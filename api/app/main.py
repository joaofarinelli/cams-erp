import asyncio
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI

from app.config import get_settings
from app.routers import agent, alerts, auth, cameras, clips, digest as digest_router, events, onboarding, pairing, privacy, rules, subscribers, webhooks
from app.services.digest import digest_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    task: asyncio.Task | None = None
    if settings.digest_enabled:
        task = asyncio.create_task(digest_scheduler(), name="digest_scheduler")
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, BaseException):
                pass


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.env,
            traces_sample_rate=0.1,
        )

    app = FastAPI(title="cams-erp API", version="0.1.0", lifespan=lifespan)
    app.include_router(cameras.router)
    app.include_router(pairing.router)
    app.include_router(pairing.devices_router)
    app.include_router(rules.router)
    app.include_router(clips.router)
    app.include_router(events.router)
    app.include_router(alerts.router)
    app.include_router(agent.router)
    app.include_router(subscribers.router)
    app.include_router(digest_router.router)
    app.include_router(onboarding.router)
    app.include_router(webhooks.router)
    app.include_router(auth.router)
    app.include_router(privacy.router)
    if settings.auth_bypass:
        from app.routers import dev_storage

        app.include_router(dev_storage.router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
