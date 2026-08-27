from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from utag_api.database import Base, get_db, new_id
from utag_api.main import app
from utag_api.models import Role, User, UserRole
from utag_api.security import hash_password
from utag_api.services.identity import seed_authorization


@pytest.fixture
async def session_factory(tmp_path):  # type: ignore[no-untyped-def]
    database_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        await seed_authorization(session)
        administrator = await session.scalar(select(Role).where(Role.key == "administrator"))
        assert administrator is not None
        user = User(
            id=new_id(),
            email="admin@example.edu.gh",
            password_hash=hash_password("StrongPassword123"),
            status="active",
            email_verified=True,
            title="Dr.",
            other_name="Ama",
            surname="Mensah",
        )
        session.add(user)
        await session.flush()
        session.add(
            UserRole(
                id=new_id(),
                user_id=user.id,
                role_id=administrator.id,
                assigned_by_id=user.id,
                assigned_at=datetime.now(UTC),
            )
        )
        await session.commit()
    yield factory
    await engine.dispose()


@pytest.fixture
async def client(session_factory, monkeypatch) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def no_rate_limit(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr("utag_api.routers.auth.enforce_rate_limit", no_rate_limit)
    # Integration tests exercise email-dependent flows by default.
    monkeypatch.setattr(
        "utag_api.services.delivery.get_settings",
        lambda: SimpleNamespace(
            smtp_host="smtp.test.example",
            smtp_username="smtp-test-user",
            smtp_password=SecretStr("smtp-test-password"),
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()
