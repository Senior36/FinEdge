from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    NEWS_API_KEY: str
    OPENROUTER_API_KEY: str
    ALPACA_API_KEY: str | None = None
    ALPACA_SECRET_KEY: str | None = None
    ALPACA_DATA_URL: str = "https://data.alpaca.markets"
    EODHD_API_KEY: str | None = None
    EODHD_BASE_URL: str = "https://eodhd.com/api"
    FUNDAMENTAL_ARTIFACT_DIR: str = "/app/artifacts/fundamental"
    FUNDAMENTAL_ANALYSIS_CACHE_HOURS: int = 24
    FUNDAMENTAL_REPORT_CACHE_DAYS: int = 7
    LLM_MODEL: str = "google/gemini-3-flash-preview"
    DATABASE_URL: str
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15


settings = Settings()
