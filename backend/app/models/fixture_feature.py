"""
Tabla de features pre-calculadas para cada partido histórico.
Las features son columnas reales (no JSON blob).
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Index, Boolean, Text
from sqlalchemy.sql import func

from app.database import Base


class FixtureFeature(Base):
    """Features pre-calculadas para partidos históricos — columnas reales de la tabla."""
    __tablename__ = "fixture_features"

    id = Column(Integer, primary_key=True, index=True)
    Date = Column("Date", String(20), nullable=True)
    HomeTeam = Column("HomeTeam", String(200), nullable=True)
    AwayTeam = Column("AwayTeam", String(200), nullable=True)
    FTR = Column("FTR", String(5), nullable=True)
    League = Column("League", String(200), nullable=True)
    Season = Column("Season", String(50), nullable=True)

    __table_args__ = (
        Index('ix_ff_teams', 'HomeTeam', 'AwayTeam'),
    )

    def __repr__(self):
        return f"<FixtureFeature {self.HomeTeam} vs {self.AwayTeam} ({self.Date})>"
