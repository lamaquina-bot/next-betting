"""
Schemas Pydantic para bankroll.
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class BankrollResponse(BaseModel):
    """Respuesta del historial de bankroll"""
    id: int
    date: date
    balance: float
    daily_pnl: float
    total_bets: int
    wins: int
    losses: int
    roi: float

    class Config:
        from_attributes = True


class BetResultRequest(BaseModel):
    """Request para registrar resultado de una apuesta"""
    value_bet_id: int
    won: bool
    stake: float = Field(..., gt=0)
    odds: float = Field(..., gt=1.0)


class BetResultResponse(BaseModel):
    """Respuesta al registrar resultado"""
    value_bet_id: int
    result: bool
    profit: float
    new_balance: float
    message: str


class DashboardSummary(BaseModel):
    """Resumen del dashboard principal"""
    current_balance: float
    total_bets: int
    wins: int
    losses: int
    win_rate: float
    roi: float
    profit_units: float
    pending_bets: int
    last_updated: Optional[datetime] = None
