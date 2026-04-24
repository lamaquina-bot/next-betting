"""
Rutas de bankroll: GET /bankroll, POST /bankroll/bet-result
Incluye protección de datos financieros (Fix 5 - HIGH).
"""
import os
from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
from app.config import settings

router = APIRouter(prefix="/bankroll", tags=["Bankroll"])



# --- Fix 5: Protección de datos financieros ---

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")  # Clave de admin (opcional)


def _is_admin(request: Request) -> bool:
    """Verificar si la petición viene de un admin mediante header."""
    if not ADMIN_API_KEY:
        # Si no hay ADMIN_API_KEY configurado, todos ven datos completos (modo dev)
        return True
    return request.headers.get("X-Admin-Key", "") == ADMIN_API_KEY


def _mask_balance(balance: float) -> float:
    """Enmascarar balance: mostrar solo magnitud relativa, no valor real."""
    if balance == 0:
        return 0.0
    # Mostrar porcentaje del bankroll inicial en vez del monto real
    return round(balance / settings.initial_bankroll * 100, 1)


def _mask_pnl(pnl: float) -> str:
    """Enmascarar PnL: mostrar solo signo, no magnitud exacta."""
    if pnl > 0:
        return "positivo"
    elif pnl < 0:
        return "negativo"
    return "neutro"


@router.get("/", response_model=list[BankrollResponse])
async def get_bankroll_history(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Últimos N días"),
    db: AsyncSession = Depends(get_db),
):
    """Obtener historial de bankroll. Datos financieros enmascarados para no-admins."""
    query = (
        select(BankrollHistory)
        .order_by(BankrollHistory.date.desc())
        .limit(days)
    )
    result = await db.execute(query)
    history = result.scalars().all()

    is_admin = _is_admin(request)

    # Si no hay historial, devolver entrada inicial como dict (sin id de BD)
    if not history:
        balance_val = settings.initial_bankroll
        pnl_val = 0.0
        if not is_admin:
            balance_val = _mask_balance(balance_val)
        return [{
            "id": 0,
            "date": date_type.today(),
            "balance": balance_val,
            "daily_pnl": pnl_val,
            "total_bets": 0,
            "wins": 0,
            "losses": 0,
            "roi": 0.0,
        }]

    # Fix 5: Enmascarar datos financieros para usuarios no-admin
    if not is_admin:
        return [{
            "id": entry.id,
            "date": entry.date,
            "balance": _mask_balance(entry.balance),
            "daily_pnl": 1.0 if entry.daily_pnl > 0 else (-1.0 if entry.daily_pnl < 0 else 0.0),
            "total_bets": entry.total_bets,
            "wins": entry.wins,
            "losses": entry.losses,
            "roi": entry.roi,
        } for entry in history]

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
        initial = settings.initial_bankroll
        bankroll.roi = ((bankroll.balance - initial) / initial) * 100 if initial > 0 else 0.0
    else:
        # Crear nueva entrada diaria
        # Obtener último balance conocido
        last_br = await db.execute(
            select(BankrollHistory).order_by(BankrollHistory.date.desc()).limit(1)
        )
        last = last_br.scalar_one_or_none()
        prev_balance = last.balance if last else settings.initial_bankroll

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
            roi=((prev_balance + profit - settings.initial_bankroll) / settings.initial_bankroll) * 100
            if settings.initial_bankroll > 0
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
