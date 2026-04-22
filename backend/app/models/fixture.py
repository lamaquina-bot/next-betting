"""
Modelos de tablas para ligas, fixtures y cuotas.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class League(Base):
    """Ligas de fútbol rastreadas"""
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    country = Column(String(100), nullable=False)
    season = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relación con fixtures
    fixtures = relationship("Fixture", back_populates="league")

    def __repr__(self):
        return f"<League {self.name} ({self.country})>"


class Fixture(Base):
    """Partidos de fútbol (pasados y futuros)"""
    __tablename__ = "fixtures"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False, index=True)
    home_team = Column(String(200), nullable=False)
    away_team = Column(String(200), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(50), default="upcoming")  # upcoming, live, finished, postponed
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relaciones
    league = relationship("League", back_populates="fixtures")
    odds = relationship("Odd", back_populates="fixture", cascade="all, delete-orphan")
    prediction = relationship("Prediction", back_populates="fixture", uselist=False)

    def __repr__(self):
        return f"<Fixture {self.home_team} vs {self.away_team} ({self.date})>"


class Odd(Base):
    """Cuotas de casas de apuestas para un fixture"""
    __tablename__ = "odds"

    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, ForeignKey("fixtures.id"), nullable=False, index=True)
    bookmaker = Column(String(100), nullable=False, default="unknown")
    home_odds = Column(Float, nullable=False)
    draw_odds = Column(Float, nullable=False)
    away_odds = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relación
    fixture = relationship("Fixture", back_populates="odds")

    def __repr__(self):
        return f"<Odd {self.bookmaker}: H={self.home_odds} D={self.draw_odds} A={self.away_odds}>"
