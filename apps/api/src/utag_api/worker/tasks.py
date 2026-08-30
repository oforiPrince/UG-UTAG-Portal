import asyncio
import hashlib
import io
import smtplib
import socket
import struct
import tempfile
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import BinaryIO
from uuid import UUID

from PIL import Image, UnidentifiedImageError
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.config import get_settings
from utag_api.database import SessionFactory, new_id
from utag_api.models import (
    Announcement,
    Article,
    BackgroundJob,
    Event,
    Gallery,
    GalleryItem,
    GoogleDriveConnection,
    MediaAsset,
    MediaVariant,
    OutboxEvent,
    Session,
    User,
)
from utag_api.observability import configure_logging, get_logger
from utag_api.security import decrypt_text
from utag_api.services import google_drive as drive
from utag_api.services.events import EventContext, record_change
from utag_api.services.notifications import deliver_announcement_notifications
from utag_api.services.storage import (
    delete_storage_objects,
    quarantine_key,
    s3_client,
    s3_encryption_args,
    safe_filename,
)
from utag_api.worker.celery_app import celery_app

settings = get_settings()
configure_logging(settings.debug)
logger = get_logger()


async def _relay_outbox(limit: int = 200) -> int:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    published = 0
    try:
        async with SessionFactory() as db:
            rows = (
                await db.scalars(
                    select(OutboxEvent)
                    .where(OutboxEvent.published_at.is_(None))
                    .order_by(OutboxEvent.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for event in rows:
                try:
                    if event.event_type == "task.dispatch":
                        task_name = event.payload.get("task_name")
                        args = event.payload.get("args", [])
                        queue = event.payload.get("queue")
                        if not isinstance(task_name, str) or not isinstance(args, list):
                            raise ValueError("Invalid task outbox payload")
                        await asyncio.to_thread(
                            celery_app.send_task,
                            task_name,
                            args=args,
                            queue=queue if isinstance(queue, str) else None,
                        )
                    else:
                        envelope = {
                            "id": str(event.id),
                            "type": event.event_type,
                            "topic": event.topic,
                            "aggregate_type": event.aggregate_type,
                            "aggregate_id": str(event.aggregate_id),
                            "payload": event.payload,
                            "occurred_at": event.created_at.isoformat(),
                        }
                        import orjson

                        await redis.publish(f"utag:{event.topic}", orjson.dumps(envelope))
                    event.published_at = datetime.now(UTC)
                    event.attempts += 1
                    event.last_error = None
                    published += 1
                except Exception as exc:
                    event.attempts += 1
                    event.last_error = str(exc)[:2_000]
                    logger.exception("outbox_publish_failed", event_id=str(event.id))
            await db.commit()
    finally:
        await redis.aclose()
    return published


@celery_app.task(  # type: ignore[misc]
    name="utag.outbox.relay", autoretry_for=(Exception,), retry_backoff=True
)
def relay_outbox() -> int:
    return asyncio.run(_relay_outbox())


@celery_app.task(  # type: ignore[misc]
    name="utag.media.delete_storage",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=10,
)
def delete_media_storage(storage_keys: list[str]) -> int:
    """Idempotently remove media bytes after their database record is committed away."""
    delete_storage_objects(storage_keys)
    return len(set(storage_keys))


@celery_app.task(name="utag.sessions.expire")  # type: ignore[misc]
def expire_sessions() -> int:
    async def expire() -> int:
        async with SessionFactory() as db:
            result = await db.execute(
                update(Session)
                .where(Session.expires_at <= datetime.now(UTC), Session.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC))
            )
            await db.commit()
            return result.rowcount  # type: ignore[attr-defined,no-any-return]

    return asyncio.run(expire())


async def _publish_scheduled_content() -> int:
    now = datetime.now(UTC)
    published = 0
    async with SessionFactory() as db:
        articles = (
            await db.scalars(
                select(Article)
                .where(
                    Article.status == "scheduled",
                    Article.published_at.is_not(None),
                    Article.published_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
        ).all()
        announcements = (
            await db.scalars(
                select(Announcement)
                .where(
                    Announcement.status == "scheduled",
                    Announcement.published_at.is_not(None),
                    Announcement.published_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
        ).all()
        events = (
            await db.scalars(
                select(Event)
                .where(
                    Event.publication_status == "scheduled",
                    Event.published_at.is_not(None),
                    Event.published_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
        ).all()

        for article in articles:
            article.status = "published"
            article.version += 1
            record_change(
                db,
                context=EventContext(actor_id=None, request_id=None),
                action="article.scheduled.published",
                resource_type="article",
                resource_id=article.id,
                topic="content",
                payload={"article_id": str(article.id), "status": "published"},
            )
            published += 1
        for announcement in announcements:
            announcement.status = "published"
            announcement.version += 1
            context = EventContext(actor_id=None, request_id=None)
            record_change(
                db,
                context=context,
                action="announcement.scheduled.published",
                resource_type="announcement",
                resource_id=announcement.id,
                topic="content",
                payload={"announcement_id": str(announcement.id), "status": "published"},
            )
            await deliver_announcement_notifications(
                db,
                announcement,
                context=context,
            )
            published += 1
        for event in events:
            event.publication_status = "published"
            event.version += 1
            record_change(
                db,
                context=EventContext(actor_id=None, request_id=None),
                action="event.scheduled.published",
                resource_type="event",
                resource_id=event.id,
                topic="content",
                payload={"event_id": str(event.id), "status": "published"},
            )
            published += 1
        await db.commit()
    return published


@celery_app.task(name="utag.content.publish_scheduled")  # type: ignore[misc]
def publish_scheduled_content() -> int:
    return asyncio.run(_publish_scheduled_content())


def _send_message(message: EmailMessage) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP is not configured")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as client:
        if settings.smtp_use_tls:
            client.starttls()
        if settings.smtp_username and settings.smtp_password:
            client.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        client.send_message(message)


@celery_app.task(  # type: ignore[misc]
    name="utag.email.password_reset",
    autoretry_for=(OSError, smtplib.SMTPException),
    retry_backoff=True,
    max_retries=5,
)
def send_password_reset(user_id: str, encrypted_token: str) -> None:
    async def load_user() -> User | None:
        async with SessionFactory() as db:
            return await db.get(User, UUID(user_id))

    user = asyncio.run(load_user())
    if user is None:
        return
    raw_token = decrypt_text(encrypted_token.encode())
    if not raw_token:
        raise RuntimeError("Password reset token could not be decrypted")
    reset_url = f"{settings.public_web_url}/reset-password?token={raw_token}"
    message = EmailMessage()
    message["Subject"] = "Reset your UG UTAG Portal password"
    message["From"] = settings.smtp_from_email
    message["To"] = user.email
    message.set_content(
        f"Hello {user.full_name},\n\n"
        "A password reset was requested for your UG UTAG Portal account. "
        f"Use this link within 30 minutes:\n\n{reset_url}\n\n"
        "If you did not request this, you can ignore this message."
    )
    _send_message(message)


@celery_app.task(  # type: ignore[misc]
    name="utag.email.invitation",
    autoretry_for=(OSError, smtplib.SMTPException),
    retry_backoff=True,
    max_retries=5,
)
def send_invitation(user_id: str, encrypted_token: str) -> None:
    async def load_user() -> User | None:
        async with SessionFactory() as db:
            return await db.get(User, UUID(user_id))

    user = asyncio.run(load_user())
    if user is None:
        return
    raw_token = decrypt_text(encrypted_token.encode())
    if not raw_token:
        raise RuntimeError("Invitation token could not be decrypted")
    invitation_url = f"{settings.public_web_url}/accept-invitation?token={raw_token}"
    message = EmailMessage()
    message["Subject"] = "Welcome to the UG UTAG Portal"
    message["From"] = settings.smtp_from_email
    message["To"] = user.email
    message.set_content(
        f"Hello {user.full_name},\n\n"
        "Your UG UTAG Portal membership account is ready. Set your password "
        f"within seven days:\n\n{invitation_url}\n"
    )
    _send_message(message)


async def _update_contact_job(job_id: UUID, **values: object) -> None:
    async with SessionFactory() as db:
        job = await db.get(BackgroundJob, job_id)
        if job is None:
            return
        for key, value in values.items():
            setattr(job, key, value)
        await db.commit()


@celery_app.task(  # type: ignore[misc]
    name="utag.contact.deliver",
    autoretry_for=(OSError, smtplib.SMTPException),
    retry_backoff=True,
    max_retries=5,
)
def deliver_contact_message(job_id: str) -> None:
    async def load_job() -> BackgroundJob | None:
        async with SessionFactory() as db:
            return await db.get(BackgroundJob, UUID(job_id))

    job = asyncio.run(load_job())
    if job is None or job.kind != "contact_message" or job.status == "completed":
        return
    data = job.input_json
    sender_name = str(data.get("name") or "Website visitor")
    sender_email = str(data.get("email") or "")
    message = EmailMessage()
    message["Subject"] = f"Contact form: {data.get('subject') or 'New message'}"
    message["From"] = settings.smtp_from_email
    message["To"] = settings.contact_recipient_email
    if sender_email:
        message["Reply-To"] = sender_email
    message.set_content(
        "A message was submitted through the UG UTAG Portal contact form.\n\n"
        f"Name: {sender_name}\n"
        f"Email: {sender_email or 'not provided'}\n"
        f"Subject: {data.get('subject') or ''}\n\n"
        f"{data.get('message') or ''}\n"
    )
    try:
        _send_message(message)
    except Exception as exc:
        asyncio.run(
            _update_contact_job(
                UUID(job_id),
                status="failed",
                error_code="contact_delivery_failed",
                error_message=str(exc)[:2_000],
            )
        )
        raise
    asyncio.run(
        _update_contact_job(
            UUID(job_id),
            status="completed",
            progress=100,
            error_code=None,
            error_message=None,
            result_json={
                "delivered": True,
                "recipient": settings.contact_recipient_email,
            },
        )
    )


def _clamav_scan(source: BinaryIO) -> None:
    if not settings.clamav_host:
        if settings.malware_scan_required:
            raise RuntimeError("Malware scanner is required but unavailable")
        return
    with socket.create_connection(
        (settings.clamav_host, settings.clamav_port), timeout=60
    ) as connection:
        connection.sendall(b"zINSTREAM\0")
        source.seek(0)
        while chunk := source.read(1024 * 1024):
            connection.sendall(struct.pack("!I", len(chunk)))
            connection.sendall(chunk)
        connection.sendall(struct.pack("!I", 0))
        response = b""
        while not response.endswith(b"\0"):
            part = connection.recv(4096)
            if not part:
                break
            response += part
    result = response.decode(errors="replace")
    if "OK" not in result or "FOUND" in result:
        raise RuntimeError(f"Malware scan rejected object: {result[:200]}")


def _image_variants(asset: MediaAsset, source_stream: BinaryIO) -> list[dict[str, object]]:
    if not asset.content_type.startswith("image/"):
        return []
    variants: list[dict[str, object]] = []
    try:
        source_stream.seek(0)
        source_file = Image.open(source_stream)
        if source_file.width * source_file.height > 40_000_000:
            raise RuntimeError("The uploaded image dimensions are too large")
        source_file.verify()
        source_stream.seek(0)
        source = Image.open(source_stream).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise RuntimeError("The uploaded image is invalid") from exc
    client = s3_client()
    # Keep source dimensions for placement validation (ad creatives, etc.).
    variants.append(
        {
            "id": new_id(),
            "asset_id": asset.id,
            "variant": "original",
            "storage_key": asset.storage_key,
            "content_type": asset.content_type,
            "byte_size": asset.byte_size,
            "width": source.width,
            "height": source.height,
            "sha256": asset.sha256,
        }
    )
    for width in (480, 960, 1600):
        if source.width < width and width != 480:
            continue
        image = source.copy()
        image.thumbnail((width, width * 2), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, "WEBP", quality=84, method=6)
        value = output.getvalue()
        variant_name = f"w{width}"
        key = f"media/{asset.id}/variants/{variant_name}.webp"
        client.put_object(
            Bucket=settings.media_bucket,
            Key=key,
            Body=value,
            ContentType="image/webp",
            Metadata={"sha256": hashlib.sha256(value).hexdigest()},
            **s3_encryption_args(),
        )
        variants.append(
            {
                "id": new_id(),
                "asset_id": asset.id,
                "variant": variant_name,
                "storage_key": key,
                "content_type": "image/webp",
                "byte_size": len(value),
                "width": image.width,
                "height": image.height,
                "sha256": hashlib.sha256(value).hexdigest(),
            }
        )
    return variants


@celery_app.task(  # type: ignore[misc]
    name="utag.media.process",
    autoretry_for=(OSError,),
    retry_backoff=True,
    max_retries=4,
)
def process_media(asset_id: str) -> None:
    async def load_asset() -> MediaAsset | None:
        async with SessionFactory() as db:
            return await db.get(MediaAsset, UUID(asset_id))

    asset = asyncio.run(load_asset())
    if asset is None or asset.status != "scanning":
        return
    client = s3_client()
    try:
        body = client.get_object(Bucket=settings.media_bucket, Key=asset.storage_key)["Body"]
        with tempfile.TemporaryFile() as quarantined:
            digest = hashlib.sha256()
            for chunk in iter(lambda: body.read(1024 * 1024), b""):
                digest.update(chunk)
                quarantined.write(chunk)
            if digest.hexdigest() != asset.sha256:
                raise RuntimeError("File checksum verification failed")
            _clamav_scan(quarantined)
            variant_rows = _image_variants(asset, quarantined)
        clean_key = f"media/{asset.id}/{safe_filename(asset.original_filename)}"
        client.copy_object(
            Bucket=settings.media_bucket,
            Key=clean_key,
            CopySource={"Bucket": settings.media_bucket, "Key": asset.storage_key},
            MetadataDirective="COPY",
            **s3_encryption_args(),
        )
    except Exception as exc:
        error_text = str(exc)[:500]

        async def reject() -> None:
            async with SessionFactory() as db:
                row = await db.get(MediaAsset, UUID(asset_id))
                if row:
                    row.status = "rejected"
                    row.metadata_json = {**row.metadata_json, "scan_error": error_text}
                    await db.commit()

        asyncio.run(reject())
        logger.exception("media_processing_rejected", asset_id=asset_id)
        return

    async def mark_ready() -> None:
        async with SessionFactory() as db:
            row = await db.get(MediaAsset, UUID(asset_id))
            if row is None:
                return
            row.storage_key = clean_key
            row.status = "ready"
            for variant in variant_rows:
                db.add(MediaVariant(**variant))
            db.add(
                OutboxEvent(
                    id=new_id(),
                    event_type="media.ready",
                    topic="media",
                    aggregate_type="media_asset",
                    aggregate_id=row.id,
                    payload={"asset_id": str(row.id), "status": "ready"},
                    created_at=datetime.now(UTC),
                )
            )
            await db.commit()

    asyncio.run(mark_ready())


async def _process_media_for_import(asset_id: UUID) -> None:
    """Run the synchronous Celery media task without nesting asyncio.run()."""
    await asyncio.to_thread(process_media, str(asset_id))


async def _refresh_processed_media(
    db: AsyncSession, asset: MediaAsset
) -> MediaAsset | None:
    """Refresh only the processed asset, preserving other importer identity state."""
    await db.refresh(asset, attribute_names=["status", "storage_key"])
    return asset if asset.status == "ready" else None


@celery_app.task(  # type: ignore[misc]
    name="utag.media.ensure_variants",
    autoretry_for=(OSError,),
    retry_backoff=True,
    max_retries=3,
)
def ensure_media_variants(asset_id: str) -> None:
    """Generate WebP display variants for an already-ready public/private image."""

    async def load() -> tuple[MediaAsset | None, set[str]]:
        async with SessionFactory() as db:
            asset = await db.get(MediaAsset, UUID(asset_id))
            if asset is None:
                return None, set()
            existing = {
                row.variant
                for row in (
                    await db.scalars(select(MediaVariant).where(MediaVariant.asset_id == asset.id))
                ).all()
            }
            return asset, existing

    asset, existing = asyncio.run(load())
    if asset is None or asset.status != "ready" or not asset.content_type.startswith("image/"):
        return
    if {"w480", "w960", "w1600"}.issubset(existing):
        return

    client = s3_client()
    body = client.get_object(Bucket=settings.media_bucket, Key=asset.storage_key)["Body"]
    with tempfile.TemporaryFile() as source:
        for chunk in iter(lambda: body.read(1024 * 1024), b""):
            source.write(chunk)
        variant_rows = [
            row for row in _image_variants(asset, source) if row["variant"] not in existing
        ]

    async def persist() -> None:
        async with SessionFactory() as db:
            row = await db.get(MediaAsset, UUID(asset_id))
            if row is None:
                return
            for variant in variant_rows:
                db.add(MediaVariant(**variant))
            await db.commit()

    asyncio.run(persist())
    logger.info(
        "media_variants_ensured",
        asset_id=asset_id,
        created=[str(row["variant"]) for row in variant_rows],
    )


@celery_app.task(  # type: ignore[misc]
    name="utag.imports.google_drive_folder",
    autoretry_for=(OSError,),
    retry_backoff=True,
    max_retries=2,
)
def import_google_drive_folder(job_id: str) -> None:
    asyncio.run(_import_google_drive_folder(UUID(job_id)))


async def _import_google_drive_folder(job_id: UUID) -> None:
    async with SessionFactory() as db:
        job = await db.get(BackgroundJob, job_id)
        if job is None or job.kind != "gallery.google_drive_import":
            return
        if job.status in {"completed", "failed"}:
            return
        job.status = "running"
        job.progress = 5
        await db.commit()

        gallery_id = UUID(str(job.input_json["gallery_id"]))
        folder_id = str(job.input_json["folder_id"])
        folder_url = str(job.input_json.get("folder_url") or "")
        connection_id = UUID(str(job.input_json["connection_id"]))
        owner_id = job.owner_id
        connection = await db.scalar(
            select(GoogleDriveConnection).where(
                GoogleDriveConnection.id == connection_id,
                GoogleDriveConnection.user_id == owner_id,
            )
        )
        gallery = await db.get(Gallery, gallery_id)
        if connection is None or gallery is None or owner_id is None:
            job.status = "failed"
            job.error_code = "import_prerequisites_missing"
            job.error_message = "Gallery or Google Drive connection is no longer available"
            await db.commit()
            return

        try:
            access_token = await drive.ensure_access_token(connection)
            await db.commit()
            importable, oversized = await drive.list_importable_images(
                access_token,
                folder_id,
                max_bytes=settings.upload_max_bytes,
            )
        except Exception as exc:
            message = getattr(exc, "message", None) or str(exc)
            code = getattr(exc, "code", None) or "google_drive_import_failed"
            job.status = "failed"
            job.error_code = str(code)[:100]
            job.error_message = str(message)[:500]
            await db.commit()
            logger.exception("google_drive_import_list_failed", job_id=str(job_id))
            return

        existing_items = list(
            (
                await db.scalars(
                    select(GalleryItem)
                    .where(GalleryItem.gallery_id == gallery.id)
                    .order_by(GalleryItem.position)
                )
            ).all()
        )
        existing_media_ids = {item.media_asset_id for item in existing_items}
        next_position = (existing_items[-1].position + 1) if existing_items else 0
        capacity = max(0, 500 - len(existing_items))
        skipped_capacity = max(0, len(importable) - capacity)
        importable = importable[:capacity]

        job.progress = 15
        job.result_json = {
            "listed": len(importable) + len(oversized) + skipped_capacity,
            "oversized": len(oversized),
            "skipped_capacity": skipped_capacity,
        }
        await db.commit()

        imported = 0
        reused = 0
        failed = 0
        attached_ids: list[str] = []
        client = s3_client()
        total = max(len(importable), 1)

        for index, file in enumerate(importable):
            try:
                access_token = await drive.ensure_access_token(connection)
                await db.commit()
                content = await drive.download_file(
                    access_token,
                    file.id,
                    max_bytes=settings.upload_max_bytes,
                )
                digest = hashlib.sha256(content).hexdigest()
                existing = await db.scalar(
                    select(MediaAsset).where(
                        MediaAsset.sha256 == digest,
                        MediaAsset.status == "ready",
                        MediaAsset.is_private.is_(False),
                        MediaAsset.content_type.like("image/%"),
                    )
                )
                if existing is not None:
                    asset = existing
                    reused += 1
                else:
                    asset_id = new_id()
                    storage_key = quarantine_key(asset_id, file.name)
                    asset = MediaAsset(
                        id=asset_id,
                        owner_id=owner_id,
                        storage_key=storage_key,
                        original_filename=safe_filename(file.name),
                        content_type=file.mime_type,
                        byte_size=len(content),
                        sha256=digest,
                        status="quarantined",
                        is_private=False,
                        metadata_json={
                            "source": "google_drive",
                            "drive_file_id": file.id,
                            "import_job_id": str(job_id),
                        },
                    )
                    db.add(asset)
                    await db.commit()
                    try:
                        client.put_object(
                            Bucket=settings.media_bucket,
                            Key=storage_key,
                            Body=content,
                            ContentType=file.mime_type,
                            Metadata={
                                "byte-size": str(len(content)),
                                "sha256": digest,
                            },
                            **s3_encryption_args(),
                        )
                    except Exception:
                        asset.status = "rejected"
                        asset.metadata_json = {
                            **asset.metadata_json,
                            "upload_error": "object_storage_unavailable",
                        }
                        await db.commit()
                        raise
                    asset.status = "scanning"
                    await db.commit()
                    processed_asset_id = asset.id
                    await _process_media_for_import(processed_asset_id)
                    refreshed = await _refresh_processed_media(db, asset)
                    if refreshed is None:
                        failed += 1
                        continue
                    asset = refreshed
                    imported += 1

                if asset.id not in existing_media_ids:
                    db.add(
                        GalleryItem(
                            id=new_id(),
                            gallery_id=gallery.id,
                            media_asset_id=asset.id,
                            position=next_position,
                            allow_download=True,
                        )
                    )
                    next_position += 1
                    existing_media_ids.add(asset.id)
                    attached_ids.append(str(asset.id))
                    gallery.version += 1
                await db.commit()
            except Exception:
                failed += 1
                logger.exception(
                    "google_drive_import_file_failed",
                    job_id=str(job_id),
                    drive_file_id=file.id,
                )
                await db.rollback()
                job = await db.get(BackgroundJob, job_id)
                gallery = await db.get(Gallery, gallery_id)
                connection = await db.scalar(
                    select(GoogleDriveConnection).where(
                        GoogleDriveConnection.id == connection_id,
                        GoogleDriveConnection.user_id == owner_id,
                    )
                )
                if job is None or gallery is None or connection is None:
                    return

            progress = 15 + int(((index + 1) / total) * 75)
            job = await db.get(BackgroundJob, job_id)
            if job is not None:
                job.progress = min(progress, 90)
                await db.commit()

        job = await db.get(BackgroundJob, job_id)
        gallery = await db.get(Gallery, gallery_id)
        if job is None or gallery is None:
            return
        if not gallery.external_album_url and folder_url:
            gallery.external_album_url = folder_url[:1000]
            gallery.version += 1
        job.status = "completed"
        job.progress = 100
        job.result_json = {
            **(job.result_json or {}),
            "imported": imported,
            "reused": reused,
            "failed": failed,
            "attached": len(attached_ids),
            "media_asset_ids": attached_ids,
            "oversized": len(oversized),
            "skipped_capacity": skipped_capacity,
            "gallery_version": gallery.version,
        }
        job.error_code = None
        job.error_message = None
        await db.commit()
        logger.info(
            "google_drive_import_completed",
            job_id=str(job_id),
            imported=imported,
            reused=reused,
            failed=failed,
            attached=len(attached_ids),
        )
