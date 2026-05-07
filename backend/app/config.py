from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/monitor"
    google_maps_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    secret_key: str = "dev-secret-key"
    log_level: str = "INFO"
    playwright_profile_path: str = "/data/playwright-profile"


settings = Settings()
