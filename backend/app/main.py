from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import fixtures, predictions, value_bets, bankroll, dashboard

app = FastAPI(
    title="NEXT API",
    description="Sistema de Inversión Cuantitativa en Apuestas Deportivas",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fixtures.router, prefix="/api/fixtures", tags=["Fixtures"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["Predictions"])
app.include_router(value_bets.router, prefix="/api/value-bets", tags=["Value Bets"])
app.include_router(bankroll.router, prefix="/api/bankroll", tags=["Bankroll"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
