# NEXT - Sistema de Inversión Cuantitativa en Apuestas Deportivas

## Setup
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Endpoints
- `GET /health` — Health check
- `GET /api/fixtures/upcoming` — Próximos partidos
- `GET /api/predictions` — Predicciones
- `GET /api/value-bets/today` — Value bets del día
- `GET /api/bankroll` — Estado del bankroll
- `GET /api/dashboard/summary` — Resumen dashboard

## Variables de entorno (.env)
```
DATABASE_URL=postgresql+asyncpg://next:next@localhost:5433/next_betting
API_FOOTBALL_KEY=your_key
ODDS_API_KEY=your_key
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
MODEL_PATH=models/latest_model.joblib
```
