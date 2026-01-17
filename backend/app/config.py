from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    NEWS_API_KEY: str
    LLM_API_KEY: str
    LLM_MODEL: str = "gemini-1.5-flash"
    DATABASE_URL: str


settings = Settings()
