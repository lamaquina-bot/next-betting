"""Servicios de ingesta de datos desde APIs externas"""
import httpx
from datetime import datetime, timedelta
from app.config import settings


async def fetch_upcoming_fixtures(league_id: int, days_ahead: int = 7) -> list[dict]:
    """Obtener fixtures próximos desde API-Football"""
    url = f"{settings.api_football_url}/fixtures"
    date_to = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    date_from = datetime.now().strftime("%Y-%m-%d")

    headers = {"x-apisports-key": settings.api_football_key}
    params = {"league": league_id, "season": datetime.now().year, "from": date_from, "to": date_to}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params, timeout=30)
        data = resp.json()

    if data.get("response"):
        return data["response"]
    return []


async def fetch_odds(fixture_id: int) -> list[dict]:
    """Obtener cuotas desde The Odds API"""
    url = f"{settings.odds_api_url}/sports/soccer/odds"
    params = {
        "apiKey": settings.odds_api_key,
        "regions": "eu",
        "markets": "h2h",
        "dateFormat": "iso",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=30)
        data = resp.json()

    # Filtrar por fixture si es posible (The Odds API no filtra por fixture_id directamente)
    return data if isinstance(data, list) else []
