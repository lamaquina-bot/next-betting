from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import fixtures, predictions, value_bets, bankroll, dashboard
from app.middleware.auth import APIKeyMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

app = FastAPI(
    title="NEXT API",
    description="Sistema de Inversión Cuantitativa en Apuestas Deportivas",
    version="1.0.0",
)

# Fix 3 - CORS restringido a orígenes específicos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "https://next.thefuckinggoat.cloud"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fix 2 - Rate limiting: 60 req/min por IP
app.add_middleware(RateLimitMiddleware)

# Fix 1 - Autenticación por API Key
app.add_middleware(APIKeyMiddleware)

app.include_router(fixtures.router, prefix="/api/fixtures", tags=["Fixtures"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["Predictions"])
app.include_router(value_bets.router, prefix="/api/value-bets", tags=["Value Bets"])
app.include_router(bankroll.router, prefix="/api/bankroll", tags=["Bankroll"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
