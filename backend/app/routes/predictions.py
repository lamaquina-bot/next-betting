"""
Rutas de predicciones: GET /predictions, GET /predictions/{id}, POST /predictions/generate
v2: Usa features pre-calculadas desde fixture_features cuando están disponibles.
"""
import json
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, text, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.prediction import Prediction
from app.models.fixture import Fixture, Odd
from app.models.fixture_feature import FixtureFeature
from app.schemas.prediction import PredictionResponse, GenerateRequest, GenerateResponse
from app.services.predictor import predictor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predictions", tags=["Predicciones"])


@router.get("/", response_model=list[PredictionResponse])
async def get_predictions(
    confidence_min: float = Query(0.0, ge=0.0, le=1.0, description="Confianza mínima"),
    outcome: Optional[str] = Query(None, pattern="^(home|draw|away)$"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Prediction)
    if confidence_min > 0:
        query = query.where(Prediction.confidence >= confidence_min)
    if outcome:
        query = query.where(Prediction.predicted_outcome == outcome)
    query = query.order_by(Prediction.confidence.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{prediction_id}", response_model=PredictionResponse)
async def get_prediction(
    prediction_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Prediction).where(Prediction.id == prediction_id))
    prediction = result.scalar_one_or_none()
    if not prediction:
        raise HTTPException(status_code=404, detail=f"Predicción {prediction_id} no encontrada")
    return prediction


@router.post("/generate", response_model=GenerateResponse)
async def generate_predictions(
    request: GenerateRequest = GenerateRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Generar predicciones para fixtures que tengan odds disponibles.
    Ahora usa features pre-calculadas desde fixture_features cuando están disponibles.
    """
    if not predictor._loaded:
        predictor.load_model()

    # Get fixtures with odds that don't have predictions yet
    subq = select(Prediction.fixture_id)
    query = (
        select(Fixture, Odd)
        .join(Odd, Fixture.id == Odd.fixture_id)
        .where(Fixture.id.notin_(subq))
    )

    if request.league_id:
        query = query.where(Fixture.league_id == request.league_id)
    if request.status:
        query = query.where(Fixture.status == request.status)

    query = query.limit(request.limit * 10)
    result = await db.execute(query)
    rows = result.all()

    # Group odds by fixture
    fixtures_odds: dict[int, dict] = {}
    for fixture, odd in rows:
        fid = fixture.id
        if fid not in fixtures_odds:
            fixtures_odds[fid] = {
                "fixture": fixture,
                "home_odds": [], "draw_odds": [], "away_odds": [],
            }
        fixtures_odds[fid]["home_odds"].append(odd.home_odds)
        fixtures_odds[fid]["draw_odds"].append(odd.draw_odds)
        fixtures_odds[fid]["away_odds"].append(odd.away_odds)

    generated = 0
    errors = 0
    used_features = 0

    for fid, data in list(fixtures_odds.items())[:request.limit]:
        fixture = data["fixture"]
        avg_h = sum(data["home_odds"]) / len(data["home_odds"])
        avg_d = sum(data["draw_odds"]) / len(data["draw_odds"])
        avg_a = sum(data["away_odds"]) / len(data["away_odds"])

        try:
            # Try to find pre-computed features for this match
            features_dict = await _find_features(db, fixture.home_team, fixture.away_team)

            if features_dict:
                pred = predictor.predict_with_features(
                    features_dict, avg_h, avg_d, avg_a, fixture.date
                )
                used_features += 1
            else:
                pred = predictor.predict(avg_h, avg_d, avg_a, fixture.date)

            outcome = predictor.map_outcome(pred["home_prob"], pred["draw_prob"], pred["away_prob"])

            prediction = Prediction(
                fixture_id=fid,
                model_version=pred.get("model_version", "unknown"),
                home_prob=pred["home_prob"],
                draw_prob=pred["draw_prob"],
                away_prob=pred["away_prob"],
                predicted_outcome=outcome,
                confidence=pred.get("confidence", max(pred["home_prob"], pred["draw_prob"], pred["away_prob"])),
            )
            db.add(prediction)
            generated += 1
        except Exception as e:
            logger.error(f"[Predict] Error on fixture {fid}: {e}")
            errors += 1
            continue

    await db.commit()
    return GenerateResponse(
        generated=generated, errors=errors,
        model_version=predictor.model_version,
    )


async def _find_features(db: AsyncSession, home_team: str, away_team: str) -> dict | None:
    """Look up pre-computed features from fixture_features table."""
    # Try exact match first
    result = await db.execute(
        select(FixtureFeature)
        .where(FixtureFeature.home_team == home_team)
        .where(FixtureFeature.away_team == away_team)
        .order_by(FixtureFeature.id.desc())
        .limit(1)
    )
    ff = result.scalar_one_or_none()
    if ff:
        return ff.get_features()

    # Try case-insensitive match
    result = await db.execute(
        select(FixtureFeature)
        .where(func.lower(FixtureFeature.home_team) == home_team.lower())
        .where(func.lower(FixtureFeature.away_team) == away_team.lower())
        .order_by(FixtureFeature.id.desc())
        .limit(1)
    )
    ff = result.scalar_one_or_none()
    if ff:
        return ff.get_features()

    return None


# ─────────────────────────────────────────────────────
# Admin endpoints for loading features & regenerating
# ─────────────────────────────────────────────────────

@router.post("/admin/load-features", tags=["Admin"])
async def load_features_from_csv(
    db: AsyncSession = Depends(get_db),
):
    """
    Load features from the embedded CSV into fixture_features table.
    The CSV is bundled in the Docker image at /app/data/features.csv
    """
    import pandas as pd
    from pathlib import Path

    csv_path = Path("/app/data/features.csv")
    if not csv_path.exists():
        raise HTTPException(404, f"CSV not found at {csv_path}")

    try:
        df = pd.read_csv(csv_path)
        logger.info(f"[LoadFeatures] CSV loaded: {len(df)} rows, {len(df.columns)} columns")

        # Identify non-feature columns
        id_cols = ['Date', 'HomeTeam', 'AwayTeam', 'FTR', 'League', 'Season',
                    'FTHG', 'FTAG', 'FTR_raw', 'home_points', 'away_points',
                    'result_code', 'goal_diff', 'total_goals', 'over_2_5', 'btts']
        feature_cols = [c for c in df.columns if c not in id_cols]

        # Check if table already has data
        count_result = await db.execute(select(func.count()).select_from(FixtureFeature))
        existing = count_result.scalar()
        if existing > 0:
            return {"status": "already_loaded", "count": existing}

        # Insert in batches
        batch_size = 500
        inserted = 0

        for start in range(0, len(df), batch_size):
            batch = df.iloc[start:start + batch_size]
            for _, row in batch.iterrows():
                features = {col: float(row[col]) if pd.notna(row[col]) else 0.0
                           for col in feature_cols}

                ff = FixtureFeature(
                    match_date=str(row.get('Date', '')),
                    home_team=str(row.get('HomeTeam', '')),
                    away_team=str(row.get('AwayTeam', '')),
                    league=str(row.get('League', '')),
                    season=str(row.get('Season', '')),
                    ftr=str(row.get('FTR', '')),
                    features_json=json.dumps(features),
                )
                db.add(ff)
                inserted += 1

            await db.flush()
            logger.info(f"[LoadFeatures] Inserted {inserted}/{len(df)}")

        await db.commit()
        return {"status": "ok", "inserted": inserted, "features_per_row": len(feature_cols)}

    except Exception as e:
        await db.rollback()
        logger.error(f"[LoadFeatures] Error: {e}")
        raise HTTPException(500, f"Error loading features: {str(e)}")


@router.post("/admin/regenerate", tags=["Admin"])
async def regenerate_predictions(
    db: AsyncSession = Depends(get_db),
):
    """
    Delete all existing predictions and regenerate using real features.
    """
    if not predictor._loaded:
        predictor.load_model()

    # Delete existing predictions
    await db.execute(delete(Prediction))
    await db.flush()
    logger.info("[Regenerate] Deleted all predictions")

    # Get all fixtures with odds
    query = (
        select(Fixture, Odd)
        .join(Odd, Fixture.id == Odd.fixture_id)
    )
    result = await db.execute(query)
    rows = result.all()

    # Group odds by fixture
    fixtures_odds: dict[int, dict] = {}
    for fixture, odd in rows:
        fid = fixture.id
        if fid not in fixtures_odds:
            fixtures_odds[fid] = {
                "fixture": fixture,
                "home_odds": [], "draw_odds": [], "away_odds": [],
            }
        fixtures_odds[fid]["home_odds"].append(odd.home_odds)
        fixtures_odds[fid]["draw_odds"].append(odd.draw_odds)
        fixtures_odds[fid]["away_odds"].append(odd.away_odds)

    generated = 0
    errors = 0
    used_features = 0

    for fid, data in fixtures_odds.items():
        fixture = data["fixture"]
        avg_h = sum(data["home_odds"]) / len(data["home_odds"])
        avg_d = sum(data["draw_odds"]) / len(data["draw_odds"])
        avg_a = sum(data["away_odds"]) / len(data["away_odds"])

        try:
            features_dict = await _find_features(db, fixture.home_team, fixture.away_team)

            if features_dict:
                pred = predictor.predict_with_features(
                    features_dict, avg_h, avg_d, avg_a, fixture.date
                )
                used_features += 1
            else:
                pred = predictor.predict(avg_h, avg_d, avg_a, fixture.date)

            outcome = predictor.map_outcome(pred["home_prob"], pred["draw_prob"], pred["away_prob"])

            prediction = Prediction(
                fixture_id=fid,
                model_version=pred.get("model_version", "unknown"),
                home_prob=pred["home_prob"],
                draw_prob=pred["draw_prob"],
                away_prob=pred["away_prob"],
                predicted_outcome=outcome,
                confidence=pred.get("confidence", max(pred["home_prob"], pred["draw_prob"], pred["away_prob"])),
            )
            db.add(prediction)
            generated += 1

            # Commit in batches
            if generated % 500 == 0:
                await db.flush()
                logger.info(f"[Regenerate] {generated}/{len(fixtures_odds)} predictions")

        except Exception as e:
            errors += 1
            continue

    await db.commit()

    # Get outcome distribution
    dist_result = await db.execute(
        select(Prediction.predicted_outcome, func.count())
        .group_by(Prediction.predicted_outcome)
    )
    distribution = dict(dist_result.all())

    return {
        "status": "ok",
        "generated": generated,
        "errors": errors,
        "used_real_features": used_features,
        "used_defaults": generated - used_features,
        "outcome_distribution": distribution,
        "model_version": predictor.model_version,
    }


@router.get("/admin/stats", tags=["Admin"])
async def prediction_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get prediction statistics including outcome distribution."""
    # Total predictions
    total = await db.execute(select(func.count()).select_from(Prediction))
    total_count = total.scalar()

    # Distribution
    dist = await db.execute(
        select(Prediction.predicted_outcome, func.count())
        .group_by(Prediction.predicted_outcome)
    )
    distribution = dict(dist.all())

    # Average probabilities
    avg_probs = await db.execute(
        select(
            func.avg(Prediction.home_prob),
            func.avg(Prediction.draw_prob),
            func.avg(Prediction.away_prob),
        )
    )
    row = avg_probs.one()
    avg_home, avg_draw, avg_away = float(row[0] or 0), float(row[1] or 0), float(row[2] or 0)

    # Features table count
    feat_count = await db.execute(select(func.count()).select_from(FixtureFeature))
    features_total = feat_count.scalar()

    return {
        "total_predictions": total_count,
        "outcome_distribution": distribution,
        "avg_probabilities": {
            "home": round(avg_home, 4),
            "draw": round(avg_draw, 4),
            "away": round(avg_away, 4),
        },
        "features_in_db": features_total,
    }
