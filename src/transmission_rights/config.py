from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8080, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    default_timezone: str = Field(default="Australia/Brisbane", alias="DEFAULT_TIMEZONE")
    default_confidence_level: float = Field(default=0.8, alias="DEFAULT_CONFIDENCE_LEVEL")
    aemo_nemweb_base_url: str = Field(
        default="https://nemweb.com.au", alias="AEMO_NEMWEB_BASE_URL"
    )

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


settings = Settings()
