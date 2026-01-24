from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    NEWS_API_KEY: str
    OPENROUTER_API_KEY: str
    LLM_MODEL: str = "google/gemini-3-flash-preview"
    DATABASE_URL: str


settings = Settings()
