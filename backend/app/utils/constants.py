"""Constantes del sistema NEXT"""

# Ligas cubiertas
LEAGUES = {
    "premier_league": {"id": 39, "name": "Premier League", "country": "England"},
    "la_liga": {"id": 140, "name": "La Liga", "country": "Spain"},
    "serie_a": {"id": 135, "name": "Serie A", "country": "Italy"},
    "bundesliga": {"id": 78, "name": "Bundesliga", "country": "Germany"},
    "ligue_1": {"id": 61, "name": "Ligue 1", "country": "France"},
    "champions_league": {"id": 2, "name": "Champions League", "country": "Europe"},
}

# Umbrales
MIN_EDGE = 0.05          # 5% mínimo para value bet
KELLY_FRACTION = 0.25     # Quarter Kelly
MAX_DRAWDOWN = 0.20        # 20% drawdown máximo
INITIAL_BANKROLL = 100000  # $100K USD inicial

# APIs
API_FOOTBALL_URL = "https://v3.football.api-sports.io"
ODDS_API_URL = "https://api.the-odds-api.com/v4"

# Telegram
TELEGRAM_API_URL = "https://api.telegram.org"
