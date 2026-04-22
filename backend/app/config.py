"""Configuración via variables de entorno"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Base de datos
    database_url: str = "postgresql+asyncpg://next:next@localhost:5433/next_betting"

    # APIs
    api_football_url: str = "https://v3.football.api-sports.io"
    api_football_key: str = ""
    odds_api_url: str = "https://api.the-odds-api.com/v4"
    odds_api_key: str = ""

    # Modelo ML
    model_path: str = "models/latest_model.joblib"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # App
    app_name: str = "NEXT API"
    debug: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
