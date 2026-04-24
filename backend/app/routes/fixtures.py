"""
Rutas de fixtures: GET /fixtures, GET /fixtures/upcoming, GET /fixtures/recent
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.fixture import Fixture, Odd, League
from app.schemas.fixture import FixtureResponse, FixtureUpcomingResponse, FixtureStatsResponse

router = APIRouter(prefix="/fixtures", tags=["Fixtures"])


@router.get("/", response_model=list[FixtureResponse])
async def get_fixtures(
    league_id: Optional[int] = None,
    status: Optional[str] = None,
    days_back: int = Query(365, ge=1, le=3650, description="Días hacia atrás"),
    days_ahead: int = Query(7, ge=0, le=30, description="Días hacia adelante"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Obtener fixtures con filtros opcionales. Por defecto muestra partidos recientes."""
    query = select(Fixture).options(selectinload(Fixture.odds))

    now = datetime.utcnow()

    if status:
        query = query.where(Fixture.status == status)
    if league_id:
        query = query.where(Fixture.league_id == league_id)

    # Rango de fechas
    date_from = now - timedelta(days=days_back)
    date_to = now + timedelta(days=days_ahead)
    query = query.where(Fixture.date >= date_from)
    query = query.where(Fixture.date <= date_to)

    query = query.order_by(Fixture.date.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    fixtures = result.scalars().all()
    return fixtures


@router.get("/upcoming", response_model=list[FixtureUpcomingResponse])
async def get_upcoming_fixtures(
    days: int = Query(7, ge=1, le=30, description="Próximos N días"),
    league_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Obtener próximos fixtures con mejores cuotas disponibles.
    Incluye también los fixtures más recientes si no hay futuros.
    """
    now = datetime.utcnow()
    until = now + timedelta(days=days)

    # Buscar fixtures futuros primero
    query = (
        select(Fixture, League.name.label("league_name"))
        .join(League, Fixture.league_id == League.id)
        .where(Fixture.date >= now)
    )

    if league_id:
        query = query.where(Fixture.league_id == league_id)

    query = query.order_by(Fixture.date.asc()).limit(100)
    result = await db.execute(query)
    rows = result.all()

    # Si no hay fixtures futuros, mostrar los más recientes
    if not rows:
        query = (
            select(Fixture, League.name.label("league_name"))
            .join(League, Fixture.league_id == League.id)
            .order_by(Fixture.date.desc())
            .limit(50)
        )
        if league_id:
            query = query.where(Fixture.league_id == league_id)
        result = await db.execute(query)
        rows = result.all()

    # Agrupar cuotas por fixture
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
                "status": fixture.status,
                "home_score": fixture.home_score,
                "away_score": fixture.away_score,
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


@router.get("/stats", response_model=FixtureStatsResponse)
async def get_fixture_stats(
    db: AsyncSession = Depends(get_db),
):
    """Estadísticas generales de fixtures"""
    # Total fixtures
    total = await db.execute(select(func.count(Fixture.id)))
    total_count = total.scalar()

    # Por status
    status_counts = await db.execute(
        select(Fixture.status, func.count(Fixture.id)).group_by(Fixture.status)
    )
    by_status = {row[0]: row[1] for row in status_counts.all()}

    # Rango de fechas
    date_range = await db.execute(
        select(func.min(Fixture.date), func.max(Fixture.date))
    )
    dr = date_range.one()

    # Total odds
    total_odds = await db.execute(select(func.count(Odd.id)))
    odds_count = total_odds.scalar()

    # Total ligas
    total_leagues = await db.execute(select(func.count(League.id)))
    leagues_count = total_leagues.scalar()

    return FixtureStatsResponse(
        total_fixtures=total_count,
        total_odds=odds_count,
        total_leagues=leagues_count,
        by_status=by_status,
        date_from=dr[0],
        date_to=dr[1],
    )
