import sentry_sdk
from fastapi import FastAPI

from app.config import get_settings
from app.routers import cameras, pairing, rules


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.env,
            traces_sample_rate=0.1,
        )

    app = FastAPI(title="cams-erp API", version="0.1.0")
    app.include_router(cameras.router)
    app.include_router(pairing.router)
    app.include_router(rules.router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
