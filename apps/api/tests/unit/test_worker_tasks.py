import asyncio
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from utag_api.database import Base, new_id
from utag_api.models import AccountToken, BackgroundJob, Notification, User
from utag_api.security import encrypt_text, hash_password, token_digest
from utag_api.services.email import BulkEmailResult
from utag_api.worker import tasks

CONTACT_INPUT = {
    "name": "Ama Mensah",
    "email": "ama@example.edu.gh",
    "subject": "Membership question",
    "message": "How do I update my membership records?",
}


def _prepare_contact_job(
    tmp_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession], UUID]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def setup() -> UUID:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            job = BackgroundJob(
                id=new_id(),
                kind="contact_message",
                status="queued",
                input_json=dict(CONTACT_INPUT),
            )
            session.add(job)
            await session.commit()
            return job.id

    return engine, factory, asyncio.run(setup())


def _load_job(factory: async_sessionmaker[AsyncSession], job_id: UUID) -> BackgroundJob:
    async def load() -> BackgroundJob:
        async with factory() as session:
            job = await session.get(BackgroundJob, job_id)
            assert job is not None
            return job

    return asyncio.run(load())


def test_password_reset_email_only_sends_a_current_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'password-reset.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    raw_token = "worker-password-reset-token-" + "a" * 40

    async def setup() -> UUID:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            user = User(
                id=new_id(),
                email="member@example.edu.gh",
                password_hash=hash_password("WorkerTestPassword123"),
                status="active",
                email_verified=True,
                other_name="Kojo",
                surname="Asare",
            )
            session.add(user)
            await session.flush()
            session.add(
                AccountToken(
                    id=new_id(),
                    user_id=user.id,
                    kind="password_reset",
                    token_hash=token_digest(raw_token),
                    created_at=datetime.now(UTC),
                    expires_at=datetime.now(UTC) + timedelta(minutes=30),
                )
            )
            await session.commit()
            return user.id

    user_id = asyncio.run(setup())
    encrypted_token = encrypt_text(raw_token)
    assert encrypted_token is not None
    sent: list[EmailMessage] = []
    monkeypatch.setattr(tasks, "SessionFactory", factory)
    monkeypatch.setattr(tasks, "_send_message", sent.append)

    tasks.send_password_reset(str(user_id), encrypted_token.decode())

    assert len(sent) == 1
    html = sent[0].get_body(preferencelist=("html",))
    assert html is not None
    assert f"/reset-password#token={raw_token}" in html.get_content()

    async def invalidate() -> None:
        async with factory() as session:
            token = await session.scalar(
                select(AccountToken).where(AccountToken.token_hash == token_digest(raw_token))
            )
            assert token is not None
            token.used_at = datetime.now(UTC)
            await session.commit()

    asyncio.run(invalidate())
    tasks.send_password_reset(str(user_id), encrypted_token.decode())
    assert len(sent) == 1
    asyncio.run(engine.dispose())


def test_deliver_contact_message_emails_secretariat_and_completes_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, job_id = _prepare_contact_job(tmp_path)
    sent: list[EmailMessage] = []
    monkeypatch.setattr(tasks, "SessionFactory", factory)
    monkeypatch.setattr(tasks, "_send_message", sent.append)

    tasks.deliver_contact_message(str(job_id))

    job = _load_job(factory, job_id)
    assert job.status == "completed"
    assert job.progress == 100
    assert job.result_json["recipient"] == tasks.settings.contact_recipient_email
    assert len(sent) == 1
    assert sent[0]["To"] == tasks.settings.contact_recipient_email
    assert sent[0]["Reply-To"] == "ama@example.edu.gh"
    assert "Membership question" in str(sent[0]["Subject"])
    plain = sent[0].get_body(preferencelist=("plain",))
    html = sent[0].get_body(preferencelist=("html",))
    assert plain is not None
    assert html is not None
    assert "How do I update my membership records?" in plain.get_content()
    assert "UTAG UG Portal" in html.get_content()
    asyncio.run(engine.dispose())


def test_deliver_contact_message_marks_job_failed_when_delivery_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, job_id = _prepare_contact_job(tmp_path)

    def broken(message: EmailMessage) -> None:
        raise smtplib.SMTPException("mailbox unavailable")

    monkeypatch.setattr(tasks, "SessionFactory", factory)
    monkeypatch.setattr(tasks, "_send_message", broken)

    with pytest.raises(smtplib.SMTPException):
        tasks.deliver_contact_message(str(job_id))

    job = _load_job(factory, job_id)
    assert job.status == "failed"
    assert job.error_code == "contact_delivery_failed"
    assert "mailbox unavailable" in (job.error_message or "")
    asyncio.run(engine.dispose())


def test_deliver_notification_email_batch_tracks_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'notification-worker.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def setup() -> UUID:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            user = User(
                id=new_id(),
                email="member@example.edu.gh",
                password_hash=hash_password("WorkerTestPassword123"),
                status="active",
                email_verified=True,
                other_name="Kojo",
                surname="Asare",
            )
            notification = Notification(
                id=new_id(),
                user_id=user.id,
                category="event",
                priority="high",
                title="Faculty seminar",
                body="<p>The seminar starts at 2:00 p.m.</p>",
                deep_link="/dashboard/events",
            )
            job = BackgroundJob(
                id=new_id(),
                kind="email.notification",
                status="queued",
                input_json={"notification_ids": [str(notification.id)]},
            )
            session.add_all([user, notification, job])
            await session.commit()
            return job.id

    job_id = asyncio.run(setup())
    captured: list[EmailMessage] = []

    def deliver(messages: list[EmailMessage]) -> BulkEmailResult:
        captured.extend(messages)
        return BulkEmailResult(sent=len(messages), failed=0, errors=())

    monkeypatch.setattr(tasks, "SessionFactory", factory)
    monkeypatch.setattr(tasks, "_send_messages", deliver)

    result = tasks.deliver_notification_email_batch(str(job_id))

    job = _load_job(factory, job_id)
    assert result == {"sent": 1, "failed": 0}
    assert job.status == "completed"
    assert job.progress == 100
    assert job.result_json == {"attempted": 1, "sent": 1, "failed": 0}
    assert captured[0]["To"] == "member@example.edu.gh"
    assert "Faculty seminar" in str(captured[0]["Subject"])
    html = captured[0].get_body(preferencelist=("html",))
    assert html is not None
    assert "Event notification" in html.get_content()

    async def mark_interrupted() -> None:
        async with factory() as session:
            interrupted = await session.get(BackgroundJob, job_id)
            assert interrupted is not None
            interrupted.status = "running"
            await session.commit()

    asyncio.run(mark_interrupted())
    assert tasks.deliver_notification_email_batch(str(job_id)) == {"sent": 0, "failed": 0}
    interrupted = _load_job(factory, job_id)
    assert interrupted.status == "failed"
    assert interrupted.error_code == "email_delivery_interrupted"
    assert len(captured) == 1
    asyncio.run(engine.dispose())


def test_delete_media_storage_delegates_all_storage_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deleted: list[str] = []
    monkeypatch.setattr(tasks, "delete_storage_objects", deleted.extend)

    removed = tasks.delete_media_storage(["media/original.png", "media/thumb.png"])

    assert removed == 2
    assert deleted == ["media/original.png", "media/thumb.png"]
