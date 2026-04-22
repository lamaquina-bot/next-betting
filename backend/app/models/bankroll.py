"""
Modelo de tabla para historial de bankroll.
"""
from sqlalchemy import Column, Integer, Float, DateTime, Date
from sqlalchemy.sql import func

from app.database import Base


class BankrollHistory(Base):
    """Historial diario del bankroll para tracking de rendimiento"""
    __tablename__ = "bankroll_history"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    balance = Column(Float, nullable=False)  # Balance del día
    daily_pnl = Column(Float, nullable=False, default=0.0)  # Ganancia/pérdida del día
    total_bets = Column(Integer, nullable=False, default=0)  # Total apuestas acumuladas
    wins = Column(Integer, nullable=False, default=0)  # Apuestas ganadas
    losses = Column(Integer, nullable=False, default=0)  # Apuestas perdidas
    roi = Column(Float, nullable=False, default=0.0)  # Retorno de inversión (%)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<BankrollHistory {self.date} balance={self.balance:.2f} roi={self.roi:.1f}%>"
