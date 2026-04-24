"""
Rutas de predicciones: GET /predictions, GET /predictions/{id}, POST /predictions/generate
"""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.prediction import Prediction
from app.models.fixture import Fixture, Odd
from app.schemas.prediction import PredictionResponse, GenerateRequest, GenerateResponse
from app.services.predictor import predictor
from app.services.value_detector import detect_value_bets
from app.services.kelly import calculate_stake

router = APIRouter(prefix="/predictions", tags=["Predicciones"])


@router.get("/", response_model=list[PredictionResponse])
async def get_predictions(
    confidence_min: float = Query(0.0, ge=0.0, le=1.0, description="Confianza mínima"),
    outcome: Optional[str] = Query(None, pattern="^(home|draw|away)$"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Obtener predicciones con filtros de confianza y resultado"""
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
    """Obtener una predicción específica por ID"""
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
    Usa el modelo XGBoost entrenado. Si no hay modelo, usa implied probabilities.
    """
    # Load model if not loaded
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

    query = query.limit(request.limit * 10)  # get more to deduplicate
    result = await db.execute(query)
    rows = result.all()

    # Group odds by fixture
    fixtures_odds: dict[int, dict] = {}
    for fixture, odd in rows:
        fid = fixture.id
        if fid not in fixtures_odds:
            fixtures_odds[fid] = {
                "fixture": fixture,
                "home_odds": [],
                "draw_odds": [],
                "away_odds": [],
            }
        fixtures_odds[fid]["home_odds"].append(odd.home_odds)
        fixtures_odds[fid]["draw_odds"].append(odd.draw_odds)
        fixtures_odds[fid]["away_odds"].append(odd.away_odds)

    generated = 0
    errors = 0

    for fid, data in list(fixtures_odds.items())[:request.limit]:
        fixture = data["fixture"]

        # Use average odds
        avg_h = sum(data["home_odds"]) / len(data["home_odds"])
        avg_d = sum(data["draw_odds"]) / len(data["draw_odds"])
        avg_a = sum(data["away_odds"]) / len(data["away_odds"])

        try:
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
            errors += 1
            continue

    await db.commit()
    return GenerateResponse(generated=generated, errors=errors, model_version=predictor.model_version)
