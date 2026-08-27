import asyncio
import smtplib
from email.message import EmailMessage
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from utag_api.database import Base, new_id
from utag_api.models import BackgroundJob
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
    assert "How do I update my membership records?" in sent[0].get_content()
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


def test_delete_media_storage_delegates_all_storage_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deleted: list[str] = []
    monkeypatch.setattr(tasks, "delete_storage_objects", deleted.extend)

    removed = tasks.delete_media_storage(["media/original.png", "media/thumb.png"])

    assert removed == 2
    assert deleted == ["media/original.png", "media/thumb.png"]
