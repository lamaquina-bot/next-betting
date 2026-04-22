"""
Rutas de fixtures: GET /fixtures, GET /fixtures/upcoming
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.fixture import Fixture, Odd, League
from app.schemas.fixture import FixtureResponse, FixtureUpcomingResponse

router = APIRouter(prefix="/fixtures", tags=["Fixtures"])


@router.get("/", response_model=list[FixtureResponse])
async def get_fixtures(
    league_id: Optional[int] = None,
    status: Optional[str] = None,
    days: int = Query(7, ge=1, le=30, description="Días hacia adelante"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Obtener fixtures con filtros opcionales"""
    query = select(Fixture).options(selectinload(Fixture.odds))

    # Filtros
    if league_id:
        query = query.where(Fixture.league_id == league_id)
    if status:
        query = query.where(Fixture.status == status)
    else:
        # Por defecto: partidos de hoy en adelante
        now = datetime.utcnow()
        query = query.where(Fixture.date >= now)
        query = query.where(Fixture.date <= now + timedelta(days=days))

    query = query.order_by(Fixture.date.asc()).limit(limit)
    result = await db.execute(query)
    fixtures = result.scalars().all()
    return fixtures


@router.get("/upcoming", response_model=list[FixtureUpcomingResponse])
async def get_upcoming_fixtures(
    days: int = Query(3, ge=1, le=14, description="Próximos N días"),
    league_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Obtener próximos fixtures con mejores cuotas disponibles.
    Endpoint principal para el dashboard.
    """
    now = datetime.utcnow()
    until = now + timedelta(days=days)

    # Query base: fixtures con sus ligas y cuotas
    query = (
        select(Fixture, League.name.label("league_name"))
        .join(League, Fixture.league_id == League.id)
        .outerjoin(Odd, Fixture.id == Odd.fixture_id)
        .where(and_(Fixture.date >= now, Fixture.date <= until, Fixture.status == "upcoming"))
    )

    if league_id:
        query = query.where(Fixture.league_id == league_id)

    query = query.order_by(Fixture.date.asc())
    result = await db.execute(query)
    rows = result.all()

    # Agrupar cuotas por fixture (mejor cuota por mercado)
    fixtures_map: dict[int, dict] = {}
    for row in rows:
        fixture: Fixture = row[0]
        league_name: str = row[1]
        fid = fixture.id

        if fid not in fixtures_map:
            fixtures_map[fid] = {
                "id": fid,
                "home_team": fixture.home_team,
                "away_team": fixture.away_team,
                "date": fixture.date,
                "league_name": league_name,
                "best_home_odds": None,
                "best_draw_odds": None,
                "best_away_odds": None,
            }

    # Obtener mejores cuotas por fixture
    for fid in fixtures_map:
        odds_query = select(Odd).where(Odd.fixture_id == fid)
        odds_result = await db.execute(odds_query)
        odds = odds_result.scalars().all()

        if odds:
            fixtures_map[fid]["best_home_odds"] = max(o.home_odds for o in odds)
            fixtures_map[fid]["best_draw_odds"] = max(o.draw_odds for o in odds)
            fixtures_map[fid]["best_away_odds"] = max(o.away_odds for o in odds)

    return list(fixtures_map.values())
