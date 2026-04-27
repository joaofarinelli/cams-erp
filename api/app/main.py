import sentry_sdk
import structlog
from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()
if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.env, traces_sample_rate=0.1)

logger = structlog.get_logger()


def create_app() -> FastAPI:
    app = FastAPI(title="cams-erp API", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
