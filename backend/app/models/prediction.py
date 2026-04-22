"""
Modelos de tablas para predicciones y apuestas de valor.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Prediction(Base):
    """Predicciones del modelo ML para cada fixture"""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, ForeignKey("fixtures.id"), nullable=False, unique=True, index=True)
    model_version = Column(String(50), nullable=False, default="v0.1-placeholder")
    home_prob = Column(Float, nullable=False)  # Probabilidad local
    draw_prob = Column(Float, nullable=False)  # Probabilidad empate
    away_prob = Column(Float, nullable=False)  # Probabilidad visitante
    predicted_outcome = Column(String(10), nullable=False)  # home, draw, away
    confidence = Column(Float, nullable=False, default=0.0)  # 0.0 a 1.0
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relaciones
    fixture = relationship("Fixture", back_populates="prediction")
    value_bets = relationship("ValueBet", back_populates="prediction", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Prediction fixture={self.fixture_id} outcome={self.predicted_outcome} conf={self.confidence:.2f}>"


class ValueBet(Base):
    """Apuestas de valor detectadas (donde edge > umbral)"""
    __tablename__ = "value_bets"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False, index=True)
    market_odds = Column(Float, nullable=False)  # Cuota del mercado
    edge = Column(Float, nullable=False)  # Edge calculado (0.05 = 5%)
    kelly_stake = Column(Float, nullable=False)  # Stake sugerido por Kelly
    recommended_bet = Column(String(10), nullable=False)  # home, draw, away
    status = Column(String(20), default="pending")  # pending, won, lost, void
    result = Column(Boolean, nullable=True)  # True=ganada, False=perdida
    profit = Column(Float, nullable=True)  # Ganancia/pérdida en unidades
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relación
    prediction = relationship("Prediction", back_populates="value_bets")

    def __repr__(self):
        return f"<ValueBet {self.recommended_bet} edge={self.edge:.2%} stake={self.kelly_stake:.3f}>"
