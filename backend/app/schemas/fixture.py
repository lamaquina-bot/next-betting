"""
Schemas Pydantic para fixtures, ligas y cuotas.
"""
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


# --- League ---
class LeagueBase(BaseModel):
    name: str
    country: str
    season: int

class LeagueResponse(LeagueBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Odd ---
class OddBase(BaseModel):
    bookmaker: str = "unknown"
    home_odds: float = Field(..., gt=0)
    draw_odds: float = Field(..., gt=0)
    away_odds: float = Field(..., gt=0)

class OddResponse(OddBase):
    id: int
    fixture_id: int
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Fixture ---
class FixtureBase(BaseModel):
    league_id: int
    home_team: str
    away_team: str
    date: datetime
    status: str = "upcoming"

class FixtureResponse(FixtureBase):
    id: int
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    created_at: Optional[datetime] = None
    odds: list[OddResponse] = []

    class Config:
        from_attributes = True

class FixtureUpcomingResponse(BaseModel):
    """Fixture resumido para listado de próximos partidos"""
    id: int
    home_team: str
    away_team: str
    date: datetime
    league_name: Optional[str] = None
    status: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    best_home_odds: Optional[float] = None
    best_draw_odds: Optional[float] = None
    best_away_odds: Optional[float] = None

    class Config:
        from_attributes = True


class FixtureStatsResponse(BaseModel):
    """Estadísticas de fixtures"""
    total_fixtures: int
    total_odds: int
    total_leagues: int
    by_status: dict[str, int] = {}
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
