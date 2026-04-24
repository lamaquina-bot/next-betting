"""
Schemas Pydantic para predicciones y apuestas de valor.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# --- Prediction ---
class PredictionResponse(BaseModel):
    id: int
    fixture_id: int
    model_version: str
    home_prob: float
    draw_prob: float
    away_prob: float
    predicted_outcome: str  # home, draw, away
    confidence: float
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GenerateRequest(BaseModel):
    """Request para generar predicciones en batch"""
    league_id: Optional[int] = None
    status: Optional[str] = None
    limit: int = Field(1000, ge=1, le=50000, description="Máximo fixtures a predecir")


class GenerateResponse(BaseModel):
    """Response de generación de predicciones"""
    generated: int
    errors: int
    model_version: str


# --- ValueBet ---
class ValueBetResponse(BaseModel):
    id: int
    prediction_id: int
    market_odds: float
    edge: float
    kelly_stake: float
    recommended_bet: str
    status: str
    result: Optional[bool] = None
    profit: Optional[float] = None
    created_at: Optional[datetime] = None
    fixture_id: Optional[int] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None

    class Config:
        from_attributes = True


class ValueBetTodayResponse(BaseModel):
    """Apuesta de valor del día con info completa"""
    id: int
    home_team: str
    away_team: str
    date: Optional[datetime] = None
    recommended_bet: str
    market_odds: float
    edge: float
    confidence: float
    kelly_stake: float

    class Config:
        from_attributes = True
