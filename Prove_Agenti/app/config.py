from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App general settings
    app_name: str = "FastAPI OpenRouter Demo"
    app_base_url: str = "http://localhost:3000"
    test_model: str = "meta-llama/llama-3.1-8b-instruct:free"

    # OpenRouter specifics
    openrouter_auth_url: str = "https://openrouter.ai/auth"
    openrouter_api_base: str = "https://openrouter.ai/api/v1"

    # Security
    secret_key: str = "cambiami-in-produzione-segreto-molto-lungo"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache()
def get_settings():
    """
    Restituisce un'istanza singleton caricata dalle variabili d'ambiente (.env).
    Carica i valori solo alla prima esecuzione e li mette in cache.
    """
    return Settings()