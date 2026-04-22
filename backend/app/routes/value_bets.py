"""
Rutas de apuestas de valor: GET /value-bets, GET /value-bets/today
"""
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.prediction import ValueBet, Prediction
from app.models.fixture import Fixture
from app.schemas.prediction import ValueBetResponse, ValueBetTodayResponse

router = APIRouter(prefix="/value-bets", tags=["Value Bets"])


@router.get("/", response_model=list[ValueBetResponse])
async def get_value_bets(
    status: Optional[str] = Query(None, regex="^(pending|won|lost|void)$"),
    min_edge: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Obtener apuestas de valor con filtros"""
    query = (
        select(ValueBet)
        .join(Prediction, ValueBet.prediction_id == Prediction.id)
        .join(Fixture, Prediction.fixture_id == Fixture.id)
    )

    if status:
        query = query.where(ValueBet.status == status)
    if min_edge > 0:
        query = query.where(ValueBet.edge >= min_edge)

    query = query.order_by(ValueBet.edge.desc()).limit(limit)
    result = await db.execute(query)
    value_bets = result.scalars().all()

    # Enriquecer con datos del fixture
    response = []
    for vb in value_bets:
        vb_dict = {
            "id": vb.id,
            "prediction_id": vb.prediction_id,
            "market_odds": vb.market_odds,
            "edge": vb.edge,
            "kelly_stake": vb.kelly_stake,
            "recommended_bet": vb.recommended_bet,
            "status": vb.status,
            "result": vb.result,
            "profit": vb.profit,
            "created_at": vb.created_at,
            "fixture_id": None,
            "home_team": None,
            "away_team": None,
        }
        # Obtener datos del fixture via prediction
        pred_result = await db.execute(
            select(Prediction).where(Prediction.id == vb.prediction_id)
        )
        pred = pred_result.scalar_one_or_none()
        if pred:
            vb_dict["fixture_id"] = pred.fixture_id
            fix_result = await db.execute(
                select(Fixture).where(Fixture.id == pred.fixture_id)
            )
            fix = fix_result.scalar_one_or_none()
            if fix:
                vb_dict["home_team"] = fix.home_team
                vb_dict["away_team"] = fix.away_team

        response.append(vb_dict)

    return response


@router.get("/today", response_model=list[ValueBetTodayResponse])
async def get_today_value_bets(
    db: AsyncSession = Depends(get_db),
):
    """
    Apuestas de valor para los partidos de hoy.
    Endpoint principal para alertas y dashboard.
    """
    today = date.today()
    tomorrow = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = tomorrow.replace(hour=23, minute=59, second=59)

    # Value bets con fixtures de hoy
    query = (
        select(ValueBet, Prediction, Fixture)
        .join(Prediction, ValueBet.prediction_id == Prediction.id)
        .join(Fixture, Prediction.fixture_id == Fixture.id)
        .where(
            and_(
                ValueBet.status == "pending",
                Fixture.date >= tomorrow,
                Fixture.date <= end_of_day,
            )
        )
        .order_by(ValueBet.edge.desc())
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        ValueBetTodayResponse(
            id=vb.id,
            home_team=fix.home_team,
            away_team=fix.away_team,
            date=fix.date,
            recommended_bet=vb.recommended_bet,
            market_odds=vb.market_odds,
            edge=vb.edge,
            confidence=pred.confidence,
            kelly_stake=vb.kelly_stake,
        )
        for vb, pred, fix in rows
    ]
