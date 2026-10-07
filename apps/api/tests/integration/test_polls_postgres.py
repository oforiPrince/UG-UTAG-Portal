"""Real PostgreSQL checks for poll locking, constraints, and migration history.

Opt in with POLLS_TEST_DATABASE_URL pointing at a disposable PostgreSQL database.
Each test creates a fresh schema and drops only that schema on completion.
"""

import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from utag_api.database import Base, get_db, new_id
from utag_api.main import app
from utag_api.models import AuditEvent, OutboxEvent, Role, Session, User, UserRole
from utag_api.models.polls import Poll, PollElectorate, PollOption, PollSelection, PollVote
from utag_api.security import token_digest
from utag_api.services import polls as polls_service
from utag_api.services.identity import seed_authorization

pytestmark = pytest.mark.skipif(
    not os.environ.get("POLLS_TEST_DATABASE_URL"),
    reason="Set POLLS_TEST_DATABASE_URL to a disposable PostgreSQL database",
)

API_ROOT = Path(__file__).resolve().parents[2]
POLL_REVISION = "k4p5o6l7l8s9"
PRE_POLL_REVISION = "j3c4h5a6t7e8"
POLL_TABLES = {
    "polls",
    "poll_options",
    "poll_electorate",
    "poll_votes",
    "poll_selections",
    "poll_deliveries",
}


@dataclass
class PostgresHarness:
    engine: AsyncEngine
    owner_engine: AsyncEngine
    factory: async_sessionmaker[AsyncSession]
    schema: str
    url: str = field(repr=False)


@dataclass
class PollScenario:
    poll_id: UUID
    option_ids: tuple[UUID, UUID]
    member_id: UUID
    member_headers: dict[str, str]
    organizer_headers: dict[str, str]


@pytest.fixture
async def postgres_schema() -> AsyncIterator[PostgresHarness]:
    url = make_url(os.environ["POLLS_TEST_DATABASE_URL"])
    if url.get_backend_name() != "postgresql":
        pytest.fail("POLLS_TEST_DATABASE_URL must point to PostgreSQL")
    schema = f"polls_test_{uuid4().hex}"
    owner_engine = create_async_engine(url)
    async with owner_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    options = f"{url.query.get('options', '')} -csearch_path={schema}".strip()
    scoped_url = url.update_query_dict({"options": options, "application_name": schema})
    engine = create_async_engine(scoped_url)
    harness = PostgresHarness(
        engine=engine,
        owner_engine=owner_engine,
        factory=async_sessionmaker(engine, expire_on_commit=False),
        schema=schema,
        url=scoped_url.render_as_string(hide_password=False),
    )
    try:
        yield harness
    finally:
        await engine.dispose()
        async with owner_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await owner_engine.dispose()


@pytest.fixture
async def postgres_client(
    postgres_schema: PostgresHarness,
) -> AsyncIterator[AsyncClient]:
    async with postgres_schema.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with postgres_schema.factory() as db:
        await seed_authorization(db)

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with postgres_schema.factory() as db:
            try:
                yield db
            except Exception:
                await db.rollback()
                raise

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous


async def create_scenario(
    harness: PostgresHarness, *, closes_at: datetime | None = None
) -> PollScenario:
    now = datetime.now(UTC)
    member_id, organizer_id, poll_id = new_id(), new_id(), new_id()
    option_ids = (new_id(), new_id())
    credentials: dict[str, dict[str, str]] = {}
    async with harness.factory() as db:
        for label, user_id, role_key in (
            ("member", member_id, "member"),
            ("organizer", organizer_id, "administrator"),
        ):
            token, csrf = f"{label}-{uuid4().hex}", uuid4().hex
            user = User(
                id=user_id,
                email=f"{label}-{uuid4().hex}@example.edu.gh",
                password_hash=token_digest("unused-by-cookie-authentication"),
                status="active",
                email_verified=True,
                other_name=label.title(),
                surname="PollTest",
            )
            db.add(user)
            await db.flush()
            role = await db.scalar(select(Role).where(Role.key == role_key))
            assert role is not None
            db.add(UserRole(user_id=user_id, role_id=role.id, assigned_at=now))
            db.add(
                Session(
                    user_id=user_id,
                    token_hash=token_digest(token),
                    csrf_hash=token_digest(csrf),
                    created_at=now,
                    last_seen_at=now,
                    expires_at=now + timedelta(hours=1),
                )
            )
            credentials[label] = {"Cookie": f"utag_session={token}", "X-CSRF-Token": csrf}
        db.add(
            Poll(
                id=poll_id,
                title="PostgreSQL integrity poll",
                question="Do you support the proposal?",
                audiences=[{"type": "member", "value": str(member_id)}],
                opens_at=now - timedelta(minutes=1),
                closes_at=closes_at or now + timedelta(hours=1),
                published_at=now - timedelta(minutes=1),
                created_by_id=organizer_id,
            )
        )
        await db.flush()
        db.add(PollElectorate(poll_id=poll_id, user_id=member_id))
        db.add_all(
            PollOption(id=option_id, poll_id=poll_id, label=label, position=position)
            for position, (option_id, label) in enumerate(
                zip(option_ids, ("YES", "NO"), strict=True)
            )
        )
        await db.commit()
    return PollScenario(
        poll_id=poll_id,
        option_ids=option_ids,
        member_id=member_id,
        member_headers=credentials["member"],
        organizer_headers=credentials["organizer"],
    )


async def vote(client: AsyncClient, scenario: PollScenario, option_id: UUID) -> Response:
    return await client.put(
        f"/api/v1/polls/{scenario.poll_id}/vote",
        headers=scenario.member_headers,
        json={"option_ids": [str(option_id)]},
    )


async def wait_for_lock_waiters(harness: PostgresHarness, count: int) -> None:
    """Prove requests reached PostgreSQL instead of relying on task scheduling."""
    async with asyncio.timeout(10):
        async with harness.owner_engine.connect() as observer:
            while True:
                waiting = await observer.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE application_name = :application_name "
                        "AND wait_event_type = 'Lock'"
                    ),
                    {"application_name": harness.schema},
                )
                # PostgreSQL statistics snapshots can be cached within a transaction.
                await observer.rollback()
                if waiting >= count:
                    return
                await asyncio.sleep(0.02)


async def ballot_count(harness: PostgresHarness, poll_id: UUID) -> int:
    async with harness.factory() as db:
        return int(
            await db.scalar(
                select(func.count()).select_from(PollVote).where(PollVote.poll_id == poll_id)
            )
            or 0
        )


@pytest.mark.parametrize("same_choice", [True, False])
async def test_concurrent_final_votes_serialize_to_one_ballot(
    postgres_schema: PostgresHarness, postgres_client: AsyncClient, same_choice: bool
) -> None:
    scenario = await create_scenario(postgres_schema)
    async with postgres_schema.factory() as gate:
        await gate.scalar(select(Poll).where(Poll.id == scenario.poll_id).with_for_update())
        first = asyncio.create_task(vote(postgres_client, scenario, scenario.option_ids[0]))
        await wait_for_lock_waiters(postgres_schema, 1)
        second = asyncio.create_task(
            vote(postgres_client, scenario, scenario.option_ids[0 if same_choice else 1])
        )
        try:
            await wait_for_lock_waiters(postgres_schema, 2)
        finally:
            await gate.rollback()
        responses = await asyncio.wait_for(asyncio.gather(first, second), timeout=10)
    assert sorted(response.status_code for response in responses) == (
        [200, 200] if same_choice else [200, 409]
    ), [response.text for response in responses]
    assert await ballot_count(postgres_schema, scenario.poll_id) == 1
    async with postgres_schema.factory() as db:
        choices = (
            await db.scalars(
                select(PollSelection.option_id).where(PollSelection.poll_id == scenario.poll_id)
            )
        ).all()
        assert choices == [scenario.option_ids[0]]
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.resource_id == scenario.poll_id,
                    AuditEvent.action == "poll.vote.recorded",
                )
            )
            == 1
        )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(
                    OutboxEvent.aggregate_id == scenario.poll_id,
                    OutboxEvent.event_type == "poll.results.changed",
                )
            )
            == 1
        )


async def test_deadline_is_rechecked_after_waiting_for_poll_lock(
    postgres_schema: PostgresHarness, postgres_client: AsyncClient
) -> None:
    closes_at = datetime.now(UTC) + timedelta(seconds=1)
    scenario = await create_scenario(postgres_schema, closes_at=closes_at)
    async with postgres_schema.factory() as gate:
        await gate.scalar(select(Poll).where(Poll.id == scenario.poll_id).with_for_update())
        pending = asyncio.create_task(vote(postgres_client, scenario, scenario.option_ids[0]))
        try:
            await wait_for_lock_waiters(postgres_schema, 1)
            await asyncio.sleep(max(0, (closes_at - datetime.now(UTC)).total_seconds()) + 0.05)
        finally:
            await gate.rollback()
        response = await asyncio.wait_for(pending, timeout=10)
    assert response.status_code == 409, response.text
    assert await ballot_count(postgres_schema, scenario.poll_id) == 0


async def test_results_recheck_extended_deadline_after_waiting_for_lock(
    postgres_schema: PostgresHarness, postgres_client: AsyncClient
) -> None:
    closes_at = datetime.now(UTC) + timedelta(seconds=1)
    scenario = await create_scenario(postgres_schema, closes_at=closes_at)
    async with postgres_schema.factory() as extension:
        poll = await extension.scalar(
            select(Poll).where(Poll.id == scenario.poll_id).with_for_update()
        )
        assert poll is not None
        # Simulate an extension begun before the old deadline, committing after it.
        poll.closes_at = closes_at + timedelta(hours=1)
        await extension.flush()
        await asyncio.sleep(max(0, (closes_at - datetime.now(UTC)).total_seconds()) + 0.05)
        pending = asyncio.create_task(
            postgres_client.get(
                f"/api/v1/polls/{scenario.poll_id}/results", headers=scenario.member_headers
            )
        )
        try:
            await wait_for_lock_waiters(postgres_schema, 1)
        finally:
            await extension.commit()
        response = await asyncio.wait_for(pending, timeout=10)
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "poll_results_hidden"


async def test_accepted_ballot_retry_after_close_is_read_only(
    postgres_schema: PostgresHarness, postgres_client: AsyncClient
) -> None:
    scenario = await create_scenario(postgres_schema)
    accepted = await vote(postgres_client, scenario, scenario.option_ids[0])
    assert accepted.status_code == 200, accepted.text
    async with postgres_schema.factory() as db:
        ballot = await db.scalar(select(PollVote).where(PollVote.poll_id == scenario.poll_id))
        assert ballot is not None
        accepted_timestamps = (ballot.created_at, ballot.updated_at)
    closed = await postgres_client.post(
        f"/api/v1/polls/{scenario.poll_id}/close",
        headers=scenario.organizer_headers,
        json={"reason": "Closing the disposable poll before retrying a lost response"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["closed_at"] is not None
    async with postgres_schema.factory() as db:
        before_retry_events = await db.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.aggregate_id == scenario.poll_id)
        )
    retried = await vote(postgres_client, scenario, scenario.option_ids[0])
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "closed"
    assert retried.json()["can_vote"] is False
    changed = await vote(postgres_client, scenario, scenario.option_ids[1])
    assert changed.status_code == 409, changed.text
    assert await ballot_count(postgres_schema, scenario.poll_id) == 1
    async with postgres_schema.factory() as db:
        ballot = await db.scalar(select(PollVote).where(PollVote.poll_id == scenario.poll_id))
        assert ballot is not None
        assert (ballot.created_at, ballot.updated_at) == accepted_timestamps
        assert (
            await db.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.aggregate_id == scenario.poll_id)
            )
            == before_retry_events
        )


@pytest.mark.parametrize("close_first", [True, False])
async def test_vote_and_early_close_share_transaction_lock(
    postgres_schema: PostgresHarness, postgres_client: AsyncClient, close_first: bool
) -> None:
    scenario = await create_scenario(postgres_schema)

    async def close() -> Response:
        return await postgres_client.post(
            f"/api/v1/polls/{scenario.poll_id}/close",
            headers=scenario.organizer_headers,
            json={"reason": "Closing this disposable test poll"},
        )

    async with postgres_schema.factory() as gate:
        await gate.scalar(select(Poll).where(Poll.id == scenario.poll_id).with_for_update())
        first = asyncio.create_task(
            close() if close_first else vote(postgres_client, scenario, scenario.option_ids[0])
        )
        await wait_for_lock_waiters(postgres_schema, 1)
        second = asyncio.create_task(
            vote(postgres_client, scenario, scenario.option_ids[0]) if close_first else close()
        )
        try:
            await wait_for_lock_waiters(postgres_schema, 2)
        finally:
            await gate.rollback()
        responses = await asyncio.wait_for(asyncio.gather(first, second), timeout=10)
    close_response, vote_response = responses if close_first else responses[::-1]
    assert close_response.status_code == 200, close_response.text
    assert vote_response.status_code == (409 if close_first else 200), vote_response.text
    assert await ballot_count(postgres_schema, scenario.poll_id) == (0 if close_first else 1)
    async with postgres_schema.factory() as db:
        poll = await db.get(Poll, scenario.poll_id)
        assert poll is not None and poll.closed_at is not None


async def test_confidential_choices_do_not_escape_audit_outbox_or_export(
    postgres_schema: PostgresHarness, postgres_client: AsyncClient
) -> None:
    scenario = await create_scenario(postgres_schema)
    response = await vote(postgres_client, scenario, scenario.option_ids[0])
    assert response.status_code == 200, response.text
    results = await postgres_client.get(
        f"/api/v1/polls/{scenario.poll_id}/results", headers=scenario.organizer_headers
    )
    assert results.status_code == 200, results.text
    assert results.json()["response_count"] == 1
    assert results.json()["named_voters"] is None
    export = await postgres_client.get(
        f"/api/v1/polls/{scenario.poll_id}/export", headers=scenario.organizer_headers
    )
    assert export.status_code == 200, export.text
    assert "PollTest" not in export.text
    assert str(scenario.member_id) not in export.text
    async with postgres_schema.factory() as db:
        events = (
            await db.scalars(
                select(OutboxEvent).where(OutboxEvent.aggregate_id == scenario.poll_id)
            )
        ).all()
        assert events
        for event in events:
            assert str(scenario.option_ids[0]) not in json.dumps(event.payload)
        audits = (
            await db.scalars(select(AuditEvent).where(AuditEvent.resource_id == scenario.poll_id))
        ).all()
        assert audits
        for audit in audits:
            assert str(scenario.option_ids[0]) not in json.dumps(audit.changes)
            assert str(scenario.option_ids[0]) not in json.dumps(audit.metadata_json)


async def test_foreign_poll_selection_is_rejected_by_database(
    postgres_schema: PostgresHarness, postgres_client: AsyncClient
) -> None:
    scenario = await create_scenario(postgres_schema)
    other = await create_scenario(postgres_schema)
    response = await vote(postgres_client, scenario, scenario.option_ids[0])
    assert response.status_code == 200, response.text
    async with postgres_schema.factory() as db:
        ballot = await db.scalar(select(PollVote).where(PollVote.poll_id == scenario.poll_id))
        assert ballot is not None
        db.add(
            PollSelection(
                vote_id=ballot.id, poll_id=scenario.poll_id, option_id=other.option_ids[0]
            )
        )
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()
    assert await ballot_count(postgres_schema, scenario.poll_id) == 1


async def test_member_deletion_cannot_cascade_away_ballot(
    postgres_schema: PostgresHarness, postgres_client: AsyncClient
) -> None:
    scenario = await create_scenario(postgres_schema)
    response = await vote(postgres_client, scenario, scenario.option_ids[0])
    assert response.status_code == 200, response.text
    async with postgres_schema.factory() as db:
        member = await db.get(User, scenario.member_id)
        assert member is not None
        await db.delete(member)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()
    assert await ballot_count(postgres_schema, scenario.poll_id) == 1


async def test_failed_vote_transaction_rolls_back_ballot_and_outbox(
    postgres_schema: PostgresHarness,
    postgres_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = await create_scenario(postgres_schema)
    original = polls_service.emit_poll_change

    def abort_vote_transaction(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        original(*args, **kwargs)
        raise RuntimeError("Injected failure before the poll transaction commits")

    monkeypatch.setattr(polls_service, "emit_poll_change", abort_vote_transaction)
    response = await vote(postgres_client, scenario, scenario.option_ids[0])
    assert response.status_code == 500, response.text
    assert await ballot_count(postgres_schema, scenario.poll_id) == 0
    async with postgres_schema.factory() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(PollSelection)
                .where(PollSelection.poll_id == scenario.poll_id)
            )
            == 0
        )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.aggregate_id == scenario.poll_id)
            )
            == 0
        )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.resource_id == scenario.poll_id)
            )
            == 0
        )


async def run_alembic(harness: PostgresHarness, *arguments: str) -> None:
    scoped_url = make_url(harness.url)
    # Alembic's existing INI interpolation rejects percent-encoded query options.
    # libpq's PGOPTIONS applies the same isolated search path without changing it.
    environment = {
        **os.environ,
        "DATABASE_URL": scoped_url.difference_update_query(["options"]).render_as_string(
            hide_password=False
        ),
        "PGOPTIONS": str(scoped_url.query["options"]),
        "ENVIRONMENT": "test",
    }
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "alembic",
        *arguments,
        cwd=API_ROOT,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
    output = (stdout + stderr).decode()
    output = output.replace(harness.url, "[isolated PostgreSQL test database]")
    output = output.replace(environment["DATABASE_URL"], "[isolated PostgreSQL test database]")
    assert process.returncode == 0, output


async def schema_table_names(harness: PostgresHarness) -> set[str]:
    async with harness.engine.connect() as connection:
        return set(
            await connection.scalars(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"
                ),
                {"schema": harness.schema},
            )
        )


async def test_poll_migration_round_trip_with_full_existing_history(
    postgres_schema: PostgresHarness,
) -> None:
    await run_alembic(postgres_schema, "upgrade", PRE_POLL_REVISION)
    async with postgres_schema.factory() as db:
        db.add_all(
            [
                Role(key="administrator", name="Administrator"),
                Role(key="executive", name="Executive"),
                Role(key="member", name="Member"),
            ]
        )
        await db.commit()
    await run_alembic(postgres_schema, "upgrade", POLL_REVISION)
    assert await schema_table_names(postgres_schema) >= POLL_TABLES
    async with postgres_schema.engine.connect() as connection:
        grants = set(
            (
                await connection.execute(
                    text(
                        "SELECT roles.key, permissions.key FROM role_permissions "
                        "JOIN roles ON roles.id = role_permissions.role_id "
                        "JOIN permissions ON permissions.id = role_permissions.permission_id "
                        "WHERE permissions.key LIKE 'polls.%'"
                    )
                )
            ).all()
        )
    assert grants == {
        (role, permission)
        for role in ("administrator", "executive")
        for permission in ("polls.manage", "polls.results", "polls.export")
    }
    await run_alembic(postgres_schema, "downgrade", PRE_POLL_REVISION)
    assert not POLL_TABLES & await schema_table_names(postgres_schema)
    async with postgres_schema.engine.connect() as connection:
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM permissions WHERE key LIKE 'polls.%'")
            )
            == 0
        )
        assert await connection.scalar(text("SELECT count(*) FROM roles")) == 3
    await run_alembic(postgres_schema, "upgrade", POLL_REVISION)
    assert await schema_table_names(postgres_schema) >= POLL_TABLES
