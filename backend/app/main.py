from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.routes import fixtures, predictions, value_bets, bankroll, dashboard
from app.middleware.auth import APIKeyMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.database import get_db, init_db
from app.models.fixture import Fixture, Odd, League
from app.services.predictor import predictor
import os

app = FastAPI(
    title="NEXT API",
    description="Sistema de Inversión Cuantitativa en Apuestas Deportivas",
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "https://next.thefuckinggoat.cloud"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.add_middleware(RateLimitMiddleware)

# Auth
app.add_middleware(APIKeyMiddleware)

# Routes
app.include_router(fixtures.router, prefix="/api/fixtures", tags=["Fixtures"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["Predictions"])
app.include_router(value_bets.router, prefix="/api/value-bets", tags=["Value Bets"])
app.include_router(bankroll.router, prefix="/api/bankroll", tags=["Bankroll"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])


@app.on_event("startup")
async def startup():
    """Cargar modelo ML al inicio"""
    model_path = os.getenv("MODEL_PATH", "models/latest_model.joblib")
    predictor.load_model(model_path)


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """Health check con estado de datos y modelo"""
    try:
        fixture_count = await db.execute(select(func.count(Fixture.id)))
        fc = fixture_count.scalar() or 0

        odds_count = await db.execute(select(func.count(Odd.id)))
        oc = odds_count.scalar() or 0

        league_count = await db.execute(select(func.count(League.id)))
        lc = league_count.scalar() or 0
    except Exception:
        fc, oc, lc = 0, 0, 0

    return {
        "status": "ok",
        "version": "2.0.0",
        "data": {
            "fixtures": fc,
            "odds": oc,
            "leagues": lc,
        },
        "model_loaded": predictor._loaded,
        "model_version": predictor.model_version if predictor._loaded else "not-loaded",
    }
