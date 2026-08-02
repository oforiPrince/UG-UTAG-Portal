import hashlib
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from starlette.concurrency import run_in_threadpool

from utag_api.config import get_settings
from utag_api.database import new_id
from utag_api.dependencies import (
    CurrentPrincipal,
    DbSession,
    Principal,
    event_context,
    require_mutation_permissions,
    require_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import MediaAsset
from utag_api.schemas.common import MessageResponse, Page
from utag_api.schemas.domain import (
    CompleteUploadRequest,
    MediaUpdate,
    MediaView,
    PresignUploadRequest,
    PresignUploadResponse,
)
from utag_api.services.events import enqueue_task, record_change
from utag_api.services.query import paginate
from utag_api.services.storage import (
    presign_get,
    presign_put,
    quarantine_key,
    s3_client,
    s3_encryption_args,
    safe_filename,
    validate_upload,
)

router = APIRouter(prefix="/media", tags=["media"])


@router.get("", response_model=Page[MediaView])
async def list_media(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("media.manage"))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
    status: str | None = None,
    q: str | None = None,
) -> Page[MediaView]:
    statement = select(MediaAsset).order_by(MediaAsset.created_at.desc())
    if status:
        statement = statement.where(MediaAsset.status == status)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                MediaAsset.original_filename.ilike(pattern),
                MediaAsset.alt_text.ilike(pattern),
                MediaAsset.content_type.ilike(pattern),
            )
        )
    result = await paginate(db, statement, page=page, page_size=page_size)
    return Page[MediaView](
        items=[MediaView.model_validate(item) for item in result.items],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        pages=result.pages,
    )


@router.post("/presign", response_model=PresignUploadResponse)
async def create_upload(
    payload: PresignUploadRequest,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("media.manage"))],
) -> PresignUploadResponse:
    validate_upload(payload.content_type, payload.byte_size)
    asset_id = new_id()
    storage_key = quarantine_key(asset_id, payload.filename)
    asset = MediaAsset(
        id=asset_id,
        owner_id=principal.user.id,
        storage_key=storage_key,
        original_filename=payload.filename,
        content_type=payload.content_type,
        byte_size=payload.byte_size,
        sha256=payload.sha256.casefold(),
        status="quarantined",
        is_private=payload.is_private,
        alt_text=payload.alt_text,
    )
    db.add(asset)
    record_change(
        db,
        context=event_context(request, principal),
        action="media.upload.created",
        resource_type="media_asset",
        resource_id=asset.id,
        topic="media",
        payload={"asset_id": str(asset.id), "status": asset.status},
    )
    await db.commit()
    url, headers = presign_put(
        storage_key=storage_key,
        content_type=payload.content_type,
        byte_size=payload.byte_size,
        sha256=payload.sha256,
    )
    return PresignUploadResponse(
        asset_id=asset.id,
        upload_url=url,
        headers=headers,
        expires_in=get_settings().presigned_url_ttl_seconds,
    )


@router.post("/upload", response_model=MediaView, status_code=201)
async def upload_media(
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("media.manage"))],
    file: Annotated[UploadFile, File()],
    is_private: Annotated[bool, Form()] = True,
    alt_text: Annotated[str | None, Form(max_length=500)] = None,
) -> MediaView:
    digest = hashlib.sha256()
    byte_size = 0
    while chunk := await file.read(1024 * 1024):
        byte_size += len(chunk)
        digest.update(chunk)
        if byte_size > get_settings().upload_max_bytes:
            raise ApiError(413, "file_too_large", "The selected file is too large")
    await file.seek(0)
    content_type = file.content_type or "application/octet-stream"
    validate_upload(content_type, byte_size)
    asset_id = new_id()
    storage_key = quarantine_key(asset_id, file.filename or "upload")
    asset = MediaAsset(
        id=asset_id,
        owner_id=principal.user.id,
        storage_key=storage_key,
        original_filename=file.filename or "upload",
        content_type=content_type,
        byte_size=byte_size,
        sha256=digest.hexdigest(),
        status="quarantined",
        is_private=is_private,
        alt_text=alt_text,
    )
    db.add(asset)
    record_change(
        db,
        context=event_context(request, principal),
        action="media.upload.created",
        resource_type="media_asset",
        resource_id=asset.id,
        topic="media",
        payload={"asset_id": str(asset.id), "status": asset.status},
    )
    await db.commit()
    try:
        await run_in_threadpool(
            lambda: s3_client().upload_fileobj(
                file.file,
                get_settings().media_bucket,
                storage_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "Metadata": {
                        "byte-size": str(byte_size),
                        "sha256": asset.sha256,
                    },
                    **s3_encryption_args(),
                },
            )
        )
    except Exception as exc:
        asset.status = "rejected"
        asset.metadata_json = {"upload_error": "object_storage_unavailable"}
        await db.commit()
        raise ApiError(503, "upload_failed", "The file could not be stored") from exc
    asset.status = "scanning"
    record_change(
        db,
        context=event_context(request, principal),
        action="media.upload.completed",
        resource_type="media_asset",
        resource_id=asset.id,
        topic="media",
        payload={"asset_id": str(asset.id), "status": asset.status},
    )
    enqueue_task(
        db,
        task_name="utag.media.process",
        aggregate_type="media_asset",
        aggregate_id=asset.id,
        args=[str(asset.id)],
        queue="media",
    )
    await db.commit()
    return MediaView.model_validate(asset)


@router.post("/complete", response_model=MessageResponse)
async def complete_upload(
    payload: CompleteUploadRequest,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("media.manage"))],
) -> MessageResponse:
    asset = await db.get(MediaAsset, payload.asset_id)
    if asset is None or (
        asset.owner_id != principal.user.id and "settings.manage" not in principal.permissions
    ):
        raise ApiError(404, "media_not_found", "Media asset not found")
    if asset.status != "quarantined":
        raise ApiError(409, "upload_already_completed", "This upload is already being processed")
    try:
        head = s3_client().head_object(Bucket=get_settings().media_bucket, Key=asset.storage_key)
    except Exception as exc:
        raise ApiError(409, "upload_missing", "The uploaded object could not be verified") from exc
    metadata = head.get("Metadata", {})
    if int(head.get("ContentLength", -1)) != asset.byte_size:
        raise ApiError(409, "upload_size_mismatch", "The uploaded file size does not match")
    if metadata.get("sha256") != asset.sha256:
        raise ApiError(409, "upload_checksum_mismatch", "The uploaded checksum does not match")
    asset.status = "scanning"
    record_change(
        db,
        context=event_context(request, principal),
        action="media.upload.completed",
        resource_type="media_asset",
        resource_id=asset.id,
        topic="media",
        payload={"asset_id": str(asset.id), "status": asset.status},
    )
    enqueue_task(
        db,
        task_name="utag.media.process",
        aggregate_type="media_asset",
        aggregate_id=asset.id,
        args=[str(asset.id)],
        queue="media",
    )
    await db.commit()
    return MessageResponse(message="Upload complete. Security scanning has started")


@router.get("/{asset_id}", response_model=MediaView)
async def get_media(
    asset_id: UUID,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("media.manage"))],
) -> MediaView:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None:
        raise ApiError(404, "media_not_found", "Media asset not found")
    return MediaView.model_validate(asset)


@router.patch("/{asset_id}", response_model=MediaView)
async def update_media(
    asset_id: UUID,
    payload: MediaUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("media.manage"))],
) -> MediaView:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None:
        raise ApiError(404, "media_not_found", "Media asset not found")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(asset, key, value)
    record_change(
        db,
        context=event_context(request, principal),
        action="media.updated",
        resource_type="media_asset",
        resource_id=asset.id,
        topic="media",
        payload={"asset_id": str(asset.id)},
        changes={key: {"to": str(value)} for key, value in changes.items()},
    )
    await db.commit()
    return MediaView.model_validate(asset)


@router.delete("/{asset_id}", response_model=MessageResponse)
async def archive_media(
    asset_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("media.manage"))],
) -> MessageResponse:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None:
        raise ApiError(404, "media_not_found", "Media asset not found")
    asset.status = "archived"
    record_change(
        db,
        context=event_context(request, principal),
        action="media.archived",
        resource_type="media_asset",
        resource_id=asset.id,
        topic="media",
        payload={"asset_id": str(asset.id)},
    )
    await db.commit()
    return MessageResponse(message="Media asset archived")


@router.get("/{asset_id}/download")
async def download_media(
    asset_id: UUID, db: DbSession, principal: CurrentPrincipal
) -> dict[str, str | int]:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None or asset.status != "ready":
        raise ApiError(404, "media_not_found", "Media asset not found")
    if (
        asset.is_private
        and asset.owner_id != principal.user.id
        and not {
            "media.manage",
            "documents.manage",
        }.intersection(principal.permissions)
    ):
        raise ApiError(404, "media_not_found", "Media asset not found")
    return {
        "url": presign_get(asset.storage_key, asset.original_filename),
        "expires_in": get_settings().presigned_url_ttl_seconds,
    }


@router.get("/{asset_id}/content")
async def stream_media(
    asset_id: UUID, db: DbSession, principal: CurrentPrincipal
) -> StreamingResponse:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None or asset.status != "ready":
        raise ApiError(404, "media_not_found", "Media asset not found")
    if (
        asset.is_private
        and asset.owner_id != principal.user.id
        and not {"media.manage", "documents.manage"}.intersection(principal.permissions)
    ):
        raise ApiError(404, "media_not_found", "Media asset not found")
    try:
        stored = await run_in_threadpool(
            lambda: s3_client().get_object(
                Bucket=get_settings().media_bucket,
                Key=asset.storage_key,
            )
        )
    except Exception as exc:
        raise ApiError(404, "media_not_found", "Media asset not found") from exc
    return StreamingResponse(
        stored["Body"].iter_chunks(chunk_size=1024 * 1024),
        media_type=asset.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename(asset.original_filename)}"',
            "Cache-Control": "private, no-store",
        },
    )
