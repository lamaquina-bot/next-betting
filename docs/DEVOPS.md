# NEXT Betting — DevOps Setup

## Coolify Project
- **Proyecto:** next-betting
- **UUID:** `kwuc2svon5d1g15cb46njlbq`
- **Environment:** production → `bos4oadg29fobt3wfydxokq8`

## Coolify App (Docker Compose)
- **App:** next-betting
- **UUID:** `ankng4ktga2antzmvdu3mwby`
- **Tipo:** Docker Compose (3 servicios)

### Servicios:
| Servicio | Puerto | Dominio |
|----------|--------|---------|
| next-api | 8000 | api.next.thefuckinggoat.cloud |
| next-dashboard | 8501 | next.thefuckinggoat.cloud |
| next-db | 5432 (internal) | Sin dominio público |

## DNS Records (pendiente agregar en Cloudflare)
```
api.next   → 89.117.33.22 → DNS Only (grey cloud)
next       → 89.117.33.22 → DNS Only (grey cloud)
```

## Variables de Entorno (configurar en Coolify)
```
DATABASE_URL=postgresql+asyncpg://next:changeme_strong_prod@next-db:5432/next_betting
API_FOOTBALL_KEY=<pedir a Gabriel>
ODDS_API_KEY=<pedir a Gabriel>
TELEGRAM_BOT_TOKEN=<pedir a Gabriel>
TELEGRAM_CHAT_ID=8525762925
API_KEY=<generar random>
MODEL_PATH=models/latest_model.joblib
```

## Deploy Steps
1. Agregar DNS records en Cloudflare
2. Configurar env vars en Coolify
3. Push code al repo (ya en github.com/lamaquina-bot/next-betting)
4. Deploy desde Coolify dashboard

## Costos
| Servicio | Costo/mes |
|----------|-----------|
| VPS (existente) | $0 |
| API-Football paid | €9.99 |
| The Odds API (free tier) | $0 |
| Total | ~€10/mes |
