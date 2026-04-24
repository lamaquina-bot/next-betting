"""
Tabla de features pre-calculadas para cada partido histórico.
"""
import json
from sqlalchemy import Column, Integer, String, Float, DateTime, Index, Text
from sqlalchemy.sql import func

from app.database import Base


class FixtureFeature(Base):
    """Features pre-calculadas para partidos históricos (185 features del modelo)"""
    __tablename__ = "fixture_features"

    id = Column(Integer, primary_key=True, index=True)
    match_date = Column(String(20), nullable=True)
    home_team = Column(String(200), nullable=True)
    away_team = Column(String(200), nullable=True)
    league = Column(String(200), nullable=True)
    season = Column(String(50), nullable=True)
    ftr = Column(String(5), nullable=True)

    # All 185 features as JSON text
    features_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_ff_teams', 'home_team', 'away_team'),
        Index('ix_ff_league', 'league'),
    )

    def get_features(self) -> dict:
        """Parse features JSON"""
        if self.features_json:
            return json.loads(self.features_json)
        return {}

    def __repr__(self):
        return f"<FixtureFeature {self.home_team} vs {self.away_team} ({self.match_date})>"
