"""
Rutas de bankroll: GET /bankroll, POST /bankroll/bet-result
"""
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.bankroll import BankrollHistory
from app.models.prediction import ValueBet, Prediction
from app.schemas.bankroll import (
    BankrollResponse,
    BetResultRequest,
    BetResultResponse,
)
from app.config import get_settings

router = APIRouter(prefix="/bankroll", tags=["Bankroll"])
settings = get_settings()


@router.get("/", response_model=list[BankrollResponse])
async def get_bankroll_history(
    days: int = Query(30, ge=1, le=365, description="Últimos N días"),
    db: AsyncSession = Depends(get_db),
):
    """Obtener historial de bankroll"""
    query = (
        select(BankrollHistory)
        .order_by(BankrollHistory.date.desc())
        .limit(days)
    )
    result = await db.execute(query)
    history = result.scalars().all()

    # Si no hay historial, devolver entrada inicial
    if not history:
        return [
            BankrollHistory(
                date=date_type.today(),
                balance=settings.DEFAULT_BANKROLL,
                daily_pnl=0.0,
                total_bets=0,
                wins=0,
                losses=0,
                roi=0.0,
            )
        ]

    return history


@router.post("/bet-result", response_model=BetResultResponse)
async def register_bet_result(
    request: BetResultRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Registrar el resultado de una apuesta.
    Actualiza el value bet, el bankroll y calcula profit.
    """
    # 1. Obtener el value bet
    vb_result = await db.execute(
        select(ValueBet).where(ValueBet.id == request.value_bet_id)
    )
    value_bet = vb_result.scalar_one_or_none()
    if not value_bet:
        raise HTTPException(status_code=404, detail=f"Value bet {request.value_bet_id} no encontrada")

    if value_bet.status != "pending":
        raise HTTPException(status_code=400, detail=f"Value bet ya resuelta: {value_bet.status}")

    # 2. Calcular profit
    if request.won:
        profit = request.stake * (request.odds - 1)  # Ganancia neta
    else:
        profit = -request.stake  # Pérdida total del stake

    # 3. Actualizar value bet
    value_bet.status = "won" if request.won else "lost"
    value_bet.result = request.won
    value_bet.profit = profit

    # 4. Actualizar bankroll
    today = date_type.today()
    br_result = await db.execute(
        select(BankrollHistory).where(BankrollHistory.date == today)
    )
    bankroll = br_result.scalar_one_or_none()

    if bankroll:
        # Actualizar entrada existente
        bankroll.balance += profit
        bankroll.daily_pnl += profit
        bankroll.total_bets += 1
        if request.won:
            bankroll.wins += 1
        else:
            bankroll.losses += 1
        # ROI = (profit total / bankroll inicial) * 100
        initial = settings.DEFAULT_BANKROLL
        bankroll.roi = ((bankroll.balance - initial) / initial) * 100 if initial > 0 else 0.0
    else:
        # Crear nueva entrada diaria
        # Obtener último balance conocido
        last_br = await db.execute(
            select(BankrollHistory).order_by(BankrollHistory.date.desc()).limit(1)
        )
        last = last_br.scalar_one_or_none()
        prev_balance = last.balance if last else settings.DEFAULT_BANKROLL

        total_bets = (last.total_bets + 1) if last else 1
        wins = ((last.wins if last else 0) + (1 if request.won else 0))
        losses = ((last.losses if last else 0) + (0 if request.won else 1))

        bankroll = BankrollHistory(
            date=today,
            balance=prev_balance + profit,
            daily_pnl=profit,
            total_bets=total_bets,
            wins=wins,
            losses=losses,
            roi=((prev_balance + profit - settings.DEFAULT_BANKROLL) / settings.DEFAULT_BANKROLL) * 100
            if settings.DEFAULT_BANKROLL > 0
            else 0.0,
        )
        db.add(bankroll)

    await db.flush()

    return BetResultResponse(
        value_bet_id=request.value_bet_id,
        result=request.won,
        profit=round(profit, 2),
        new_balance=round(bankroll.balance, 2),
        message=f"✅ Apuesta ganada! Profit: +{profit:.2f}u" if request.won
        else f"❌ Apuesta perdida. Pérdida: {profit:.2f}u",
    )
