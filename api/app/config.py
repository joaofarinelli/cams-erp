from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CAMS_", env_file=".env", extra="ignore")

    env: str = Field(default="dev")
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost/camserp")
    clips_bucket: str = Field(default="cams-erp-staging-clips")
    events_queue_url: str = Field(default="")
    cognito_user_pool_id: str = Field(default="")
    cognito_jwks_url: str = Field(default="")
    aws_region: str = Field(default="sa-east-1")
    aws_endpoint_url: str = Field(default="")
    jwt_secret: str = Field(default="dev-secret-change-me")
    sentry_dsn: str = Field(default="")
    log_level: str = Field(default="INFO")
    auth_bypass: bool = Field(default=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
