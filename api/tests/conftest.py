import os

os.environ.setdefault("CAMS_ENV", "test")

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.base import Base
from app.db.models import Camera, Device, User
from app.db.session import SessionLocal, get_db
from app.main import create_app
from app.security.cognito import get_current_user


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest_asyncio.fixture
async def db_session():  # type: ignore[no-untyped-def]
    settings = get_settings()
    engine = create_async_engine(settings.database_url.replace("+psycopg", "+asyncpg"))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    session_local = async_sessionmaker(engine, expire_on_commit=False)
    async with session_local() as session:
        session.info["session_local"] = session_local
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def seed_user(db_session) -> User:
    user = User(cognito_sub="test-sub", email="test@cams-erp.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seed_device(db_session, seed_user) -> Device:
    device = Device(owner_id=seed_user.id, name="PDV 1")
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)
    return device


@pytest_asyncio.fixture
async def seed_camera(db_session, seed_device) -> Camera:
    cam = Camera(device_id=seed_device.id, name="C1", rtsp_url_encrypted="ZGV2OnRlc3Q=")
    db_session.add(cam)
    await db_session.commit()
    await db_session.refresh(cam)
    return cam


@pytest_asyncio.fixture
async def auth_client(seed_user, db_session) -> AsyncClient:
    app = create_app()

    async def override_user() -> User:
        return seed_user

    session_local = db_session.info["session_local"]

    async def override_get_db():
        async with session_local() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def anon_client(db_session) -> AsyncClient:
    app = create_app()

    session_local = db_session.info["session_local"]

    async def override_get_db():
        async with session_local() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
