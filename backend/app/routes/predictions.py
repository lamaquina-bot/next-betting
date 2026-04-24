"""
Rutas de predicciones: GET /predictions, GET /predictions/{id}, POST /predictions/generate
v3: Lee features desde fixture_features (columnas reales, no JSON).
"""
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.prediction import Prediction
from app.models.fixture import Fixture, Odd
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


async def _get_features_for_match(db: AsyncSession, feature_names: list[str],
                                   home_team: str, away_team: str) -> dict | None:
    """
    Query fixture_features for the most recent match between these teams.
    Returns a dict of {feature_name: value} for all model features.
    """
    # Build column list: always include id, and all feature_names that exist in the table
    # Use raw SQL for flexibility
    cols_str = ", ".join(f'"{c}"' for c in feature_names)
    query = text(f"""
        SELECT {cols_str}
        FROM fixture_features
        WHERE "HomeTeam" ILIKE :home AND "AwayTeam" ILIKE :away
        ORDER BY id DESC
        LIMIT 1
    """)
    try:
        result = await db.execute(query, {"home": home_team, "away": away_team})
        row = result.mappings().first()
        if row:
            return {k: float(v) if v is not None else None for k, v in row.items()}
    except Exception as e:
        logger.warning(f"[Features] Query error for {home_team} vs {away_team}: {e}")
        # Some columns might not exist — try again with only existing columns
        pass

    # Fallback: try with just the columns that exist
    try:
        # Get actual column names from DB
        col_result = await db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'fixture_features'
        """))
        db_cols = {r[0] for r in col_result.all()}

        available = [f for f in feature_names if f in db_cols]
        if not available:
            return None

        cols_str = ", ".join(f'"{c}"' for c in available)
        query = text(f"""
            SELECT {cols_str}
            FROM fixture_features
            WHERE "HomeTeam" ILIKE :home AND "AwayTeam" ILIKE :away
            ORDER BY id DESC
            LIMIT 1
        """)
        result = await db.execute(query, {"home": home_team, "away": away_team})
        row = result.mappings().first()
        if row:
            return {k: float(v) if v is not None else None for k, v in row.items()}
    except Exception as e2:
        logger.warning(f"[Features] Fallback query error: {e2}")

    return None


async def _get_median_features(db: AsyncSession, feature_names: list[str]) -> dict:
    """Compute median for each feature across all rows for fallback."""
    try:
        col_result = await db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'fixture_features'
        """))
        db_cols = {r[0] for r in col_result.all()}

        available = [f for f in feature_names if f in db_cols]
        if not available:
            return {}

        # Compute medians using percentile_cont
        median_exprs = ", ".join(
            f'percentile_cont(0.5) WITHIN GROUP (ORDER BY "{c}") as "{c}"'
            for c in available
        )
        result = await db.execute(text(f"SELECT {median_exprs} FROM fixture_features"))
        row = result.mappings().first()
        if row:
            return {k: float(v) if v is not None else 0.0 for k, v in row.items()}
    except Exception as e:
        logger.warning(f"[MedianFeatures] Error: {e}")
    return {}


@router.post("/generate", response_model=GenerateResponse)
async def generate_predictions(
    request: GenerateRequest = GenerateRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Generar predicciones para fixtures con odds, usando features de fixture_features."""
    if not predictor._loaded:
        predictor.load_model()

    feature_names = predictor.feature_names or []
    median_features = await _get_median_features(db, feature_names)

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
            features_dict = await _get_features_for_match(
                db, feature_names, fixture.home_team, fixture.away_team
            )

            if features_dict:
                # Merge: features from DB + median for missing
                merged = {}
                for fn in feature_names:
                    v = features_dict.get(fn)
                    if v is not None:
                        merged[fn] = v
                    elif fn in median_features:
                        merged[fn] = median_features[fn]
                    else:
                        merged[fn] = 0.0

                pred = predictor.predict_with_features(
                    merged, avg_h, avg_d, avg_a, fixture.date
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


@router.post("/admin/regenerate", tags=["Admin"])
async def regenerate_predictions(
    db: AsyncSession = Depends(get_db),
):
    """Delete all existing predictions and regenerate using real features from fixture_features."""
    if not predictor._loaded:
        predictor.load_model()

    feature_names = predictor.feature_names or []
    median_features = await _get_median_features(db, feature_names)

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
            features_dict = await _get_features_for_match(
                db, feature_names, fixture.home_team, fixture.away_team
            )

            if features_dict:
                merged = {}
                for fn in feature_names:
                    v = features_dict.get(fn)
                    if v is not None:
                        merged[fn] = v
                    elif fn in median_features:
                        merged[fn] = median_features[fn]
                    else:
                        merged[fn] = 0.0
                pred = predictor.predict_with_features(
                    merged, avg_h, avg_d, avg_a, fixture.date
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

            if generated % 500 == 0:
                await db.flush()
                logger.info(f"[Regenerate] {generated}/{len(fixtures_odds)} predictions")

        except Exception as e:
            logger.error(f"[Regenerate] Error fixture {fid}: {e}")
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
    total = await db.execute(select(func.count()).select_from(Prediction))
    total_count = total.scalar()

    dist = await db.execute(
        select(Prediction.predicted_outcome, func.count())
        .group_by(Prediction.predicted_outcome)
    )
    distribution = dict(dist.all())

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
    feat_count = await db.execute(text('SELECT COUNT(*) FROM fixture_features'))
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
