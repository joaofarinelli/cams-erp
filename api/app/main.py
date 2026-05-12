import asyncio
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import agent, alerts, auth, billing, cameras, clips, digest as digest_router, events, faces, onboarding, pairing, privacy, rules, subscribers, usage as usage_router, webhooks
from app.services.account_purge import account_purge_scheduler
from app.services.clip_retention import clip_retention_scheduler
from app.services.digest import digest_scheduler
from app.services.trial_expiry import trial_expiry_scheduler
from app.services.usage_aggregator import usage_storage_aggregator


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    tasks: list[asyncio.Task] = []
    if settings.digest_enabled:
        tasks.append(asyncio.create_task(digest_scheduler(), name="digest_scheduler"))
    tasks.append(asyncio.create_task(usage_storage_aggregator(), name="usage_aggregator"))
    tasks.append(asyncio.create_task(trial_expiry_scheduler(), name="trial_expiry"))
    tasks.append(asyncio.create_task(account_purge_scheduler(), name="account_purge"))
    tasks.append(asyncio.create_task(clip_retention_scheduler(), name="clip_retention"))
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
            try:
                await t
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
    if settings.cors_allowed_origins or settings.cors_allowed_origin_regex:
        origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_origin_regex=settings.cors_allowed_origin_regex or None,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
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
    app.include_router(faces.router)
    app.include_router(usage_router.router)
    app.include_router(billing.router)
    app.include_router(billing.webhooks_router)
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
