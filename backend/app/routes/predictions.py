"""
Rutas de predicciones: GET /predictions, GET /predictions/{id}
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.prediction import Prediction
from app.models.fixture import Fixture
from app.schemas.prediction import PredictionResponse

router = APIRouter(prefix="/predictions", tags=["Predicciones"])


@router.get("/", response_model=list[PredictionResponse])
async def get_predictions(
    confidence_min: float = Query(0.0, ge=0.0, le=1.0, description="Confianza mínima"),
    outcome: Optional[str] = Query(None, regex="^(home|draw|away)$"),
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
