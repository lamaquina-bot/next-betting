"""
Ruta del dashboard: GET /dashboard/summary
Resumen general para la UI principal.
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.bankroll import BankrollHistory
from app.models.prediction import ValueBet
from app.models.fixture import Fixture
from app.schemas.bankroll import DashboardSummary
from app.config import get_settings

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
settings = get_settings()


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
):
    """
    Resumen del dashboard: balance, stats, apuestas pendientes.
    """
    # Último registro de bankroll
    br_result = await db.execute(
        select(BankrollHistory).order_by(BankrollHistory.date.desc()).limit(1)
    )
    bankroll = br_result.scalar_one_or_none()

    # Apuestas pendientes
    pending_result = await db.execute(
        select(func.count(ValueBet.id)).where(ValueBet.status == "pending")
    )
    pending_bets = pending_result.scalar() or 0

    if bankroll:
        total = bankroll.wins + bankroll.losses
        win_rate = (bankroll.wins / total * 100) if total > 0 else 0.0
        return DashboardSummary(
            current_balance=round(bankroll.balance, 2),
            total_bets=bankroll.total_bets,
            wins=bankroll.wins,
            losses=bankroll.losses,
            win_rate=round(win_rate, 1),
            roi=round(bankroll.roi, 2),
            profit_units=round(bankroll.balance - settings.DEFAULT_BANKROLL, 2),
            pending_bets=pending_bets,
            last_updated=bankroll.created_at,
        )

    # Sin datos: devolver estado inicial
    return DashboardSummary(
        current_balance=settings.DEFAULT_BANKROLL,
        total_bets=0,
        wins=0,
        losses=0,
        win_rate=0.0,
        roi=0.0,
        profit_units=0.0,
        pending_bets=pending_bets,
        last_updated=datetime.utcnow(),
    )
