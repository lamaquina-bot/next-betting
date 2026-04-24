"""Configuración via variables de entorno"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Base de datos
    database_url: str = "postgresql+asyncpg://next:changeme_strong_prod@next-db-svc:5432/next_betting"

    # Modelo ML
    model_path: str = "models/latest_model.joblib"

    # APIs
    api_football_url: str = "https://v3.football.api-sports.io"
    api_football_key: str = ""
    odds_api_url: str = "https://api.the-odds-api.com/v4"
    odds_api_key: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Bankroll
    initial_bankroll: float = 100000

    # App
    app_name: str = "NEXT API"
    debug: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
