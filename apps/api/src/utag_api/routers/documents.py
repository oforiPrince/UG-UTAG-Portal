from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import func, select

from utag_api.database import new_id
from utag_api.dependencies import (
    DbSession,
    Principal,
    event_context,
    require_mutation_permissions,
    require_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import Document, DocumentFile, MediaAsset
from utag_api.schemas.common import MessageResponse, Page
from utag_api.schemas.domain import (
    DocumentCreate,
    DocumentUpdate,
    DocumentVersionCreate,
    DocumentView,
)
from utag_api.services.content import sanitize_html
from utag_api.services.events import record_change
from utag_api.services.moderation import ensure_publish_permission
from utag_api.services.query import paginate

router = APIRouter(prefix="/documents", tags=["documents"])


def audiences_allow(audiences: list[dict[str, str]], principal: Principal) -> bool:
    if "documents.manage" in principal.permissions:
        return True
    if not audiences:
        return True
    unit_ids = {
        str(value)
        for value in (
            principal.user.school_id,
            principal.user.college_id,
            principal.user.department_id,
        )
        if value
    }
    for audience in audiences:
        kind = audience.get("type")
        value = audience.get("value")
        if kind in {"all_members", "everyone"}:
            return True
        if kind == "role" and value in principal.roles:
            return True
        if kind == "unit" and value in unit_ids:
            return True
        if kind == "user" and value == str(principal.user.id):
            return True
    return False


def audience_allows(document: Document, principal: Principal) -> bool:
    return audiences_allow(document.audiences, principal)


async def document_view(db: DbSession, item: Document) -> DocumentView:
    latest_version = await db.scalar(
        select(func.max(DocumentFile.version_number)).where(DocumentFile.document_id == item.id)
    )
    latest_rows = (
        (
            await db.execute(
                select(DocumentFile, MediaAsset)
                .join(MediaAsset, MediaAsset.id == DocumentFile.media_asset_id)
                .where(
                    DocumentFile.document_id == item.id,
                    DocumentFile.version_number == latest_version,
                )
                .order_by(DocumentFile.position)
            )
        ).all()
        if latest_version is not None
        else []
    )
    files = [
        {
            "media_asset_id": asset.id,
            "filename": asset.original_filename,
            "content_type": asset.content_type,
            "byte_size": asset.byte_size,
            "content_url": f"/api/v1/media/{asset.id}/content",
        }
        for _file, asset in latest_rows
    ]
    return DocumentView.model_validate(
        {
            **item.__dict__,
            "latest_media_asset_id": files[0]["media_asset_id"] if files else None,
            "latest_filename": files[0]["filename"] if files else None,
            "files": files,
        }
    )


async def ready_document_assets(db: DbSession, asset_ids: list[UUID]) -> list[MediaAsset]:
    unique_ids = list(dict.fromkeys(asset_ids))
    assets = list((await db.scalars(select(MediaAsset).where(MediaAsset.id.in_(unique_ids)))).all())
    if len(assets) != len(unique_ids) or any(asset.status != "ready" for asset in assets):
        raise ApiError(
            409,
            "media_not_ready",
            "Every selected file must complete security scanning first",
        )
    by_id = {asset.id: asset for asset in assets}
    return [by_id[asset_id] for asset_id in unique_ids]


@router.get("", response_model=Page[DocumentView])
async def list_documents(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("documents.view"))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    category: str | None = None,
    q: str | None = None,
) -> Page[DocumentView]:
    statement = select(Document).where(Document.status != "archived")
    if category:
        statement = statement.where(Document.category == category)
    if q:
        statement = statement.where(Document.title.ilike(f"%{q.strip()}%"))
    statement = statement.order_by(Document.document_date.desc(), Document.created_at.desc())
    # Fetch extra rows before applying audience rules, then paginate the authorized subset.
    result = await paginate(db, statement, page=page, page_size=min(page_size * 3, 100))
    authorized = [item for item in result.items if audience_allows(item, principal)]
    views = [await document_view(db, item) for item in authorized[:page_size]]
    return Page[DocumentView](
        items=views,
        page=page,
        page_size=page_size,
        total=len(views) if result.pages == 1 else result.total,
        pages=result.pages,
    )


@router.get("/{document_id}", response_model=DocumentView)
async def get_document(
    document_id: UUID,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("documents.view"))],
) -> DocumentView:
    item = await db.get(Document, document_id)
    if item is None or not audience_allows(item, principal):
        raise ApiError(404, "document_not_found", "Document not found")
    return await document_view(db, item)


@router.get("/{document_id}/versions")
async def document_versions(
    document_id: UUID,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("documents.view"))],
) -> list[dict[str, object]]:
    document = await db.get(Document, document_id)
    if document is None or not audience_allows(document, principal):
        raise ApiError(404, "document_not_found", "Document not found")
    rows = (
        await db.execute(
            select(DocumentFile, MediaAsset)
            .join(MediaAsset, MediaAsset.id == DocumentFile.media_asset_id)
            .where(DocumentFile.document_id == document.id)
            .order_by(DocumentFile.version_number.desc(), DocumentFile.position)
        )
    ).all()
    return [
        {
            "id": version.id,
            "version_number": version.version_number,
            "position": version.position,
            "change_note": version.change_note,
            "media_asset_id": asset.id,
            "filename": asset.original_filename,
            "content_type": asset.content_type,
            "byte_size": asset.byte_size,
            "status": asset.status,
            "created_at": version.created_at,
        }
        for version, asset in rows
    ]


@router.post("", response_model=DocumentView, status_code=201)
async def create_document(
    payload: DocumentCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("documents.manage"))],
) -> DocumentView:
    ensure_publish_permission(principal.permissions, payload.status)
    assets = await ready_document_assets(db, payload.media_asset_ids)
    document = Document(
        id=new_id(),
        public_id=f"UTAG-{str(new_id()).split('-')[0].upper()}",
        title=payload.title,
        category=payload.category,
        sender=payload.sender,
        receiver=payload.receiver,
        description_html=sanitize_html(payload.description_html),
        document_date=payload.document_date,
        status=payload.status,
        audiences=payload.audiences,
        retention_class=payload.retention_class,
        legal_hold=payload.legal_hold,
        uploaded_by_id=principal.user.id,
    )
    db.add(document)
    await db.flush()
    db.add_all(
        [
            DocumentFile(
                id=new_id(),
                document_id=document.id,
                media_asset_id=asset.id,
                version_number=1,
                position=position,
                change_note=payload.change_note,
                uploaded_by_id=principal.user.id,
            )
            for position, asset in enumerate(assets)
        ]
    )
    record_change(
        db,
        context=event_context(request, principal),
        action="document.created",
        resource_type="document",
        resource_id=document.id,
        topic="documents",
        payload={"document_id": str(document.id), "category": document.category},
    )
    await db.commit()
    return await document_view(db, document)


@router.patch("/{document_id}", response_model=DocumentView)
async def update_document(
    document_id: UUID,
    payload: DocumentUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("documents.manage"))],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DocumentView:
    document = await db.get(Document, document_id)
    if document is None:
        raise ApiError(404, "document_not_found", "Document not found")
    if if_match != f'"{document.version}"':
        raise ApiError(412, "version_conflict", "Refresh this document before saving")
    changes = payload.model_dump(exclude_unset=True)
    ensure_publish_permission(principal.permissions, changes.get("status"))
    if "description_html" in changes:
        changes["description_html"] = sanitize_html(changes["description_html"])
    for key, value in changes.items():
        setattr(document, key, value)
    document.version += 1
    record_change(
        db,
        context=event_context(request, principal),
        action="document.updated",
        resource_type="document",
        resource_id=document.id,
        topic="documents",
        payload={"document_id": str(document.id), "version": document.version},
        changes={key: {"to": str(value)} for key, value in changes.items()},
    )
    await db.commit()
    return await document_view(db, document)


@router.delete("/{document_id}", response_model=MessageResponse)
async def archive_document(
    document_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("documents.manage"))],
) -> MessageResponse:
    document = await db.get(Document, document_id)
    if document is None:
        raise ApiError(404, "document_not_found", "Document not found")
    if document.legal_hold:
        raise ApiError(409, "legal_hold", "Remove the legal hold before archiving this document")
    document.status = "archived"
    document.version += 1
    record_change(
        db,
        context=event_context(request, principal),
        action="document.archived",
        resource_type="document",
        resource_id=document.id,
        topic="documents",
        payload={"document_id": str(document.id)},
    )
    await db.commit()
    return MessageResponse(message="Document archived")


@router.post("/{document_id}/versions", response_model=DocumentView)
async def add_document_version(
    document_id: UUID,
    payload: DocumentVersionCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("documents.manage"))],
) -> DocumentView:
    document = await db.get(Document, document_id)
    if document is None:
        raise ApiError(404, "document_not_found", "Document not found")
    assets = await ready_document_assets(db, payload.asset_ids)
    current_version = int(
        (
            await db.scalar(
                select(func.max(DocumentFile.version_number)).where(
                    DocumentFile.document_id == document.id
                )
            )
        )
        or 0
    )
    next_version = current_version + 1
    db.add_all(
        [
            DocumentFile(
                id=new_id(),
                document_id=document.id,
                media_asset_id=asset.id,
                version_number=next_version,
                position=position,
                change_note=payload.change_note,
                uploaded_by_id=principal.user.id,
            )
            for position, asset in enumerate(assets)
        ]
    )
    document.version += 1
    record_change(
        db,
        context=event_context(request, principal),
        action="document.version.created",
        resource_type="document",
        resource_id=document.id,
        topic="documents",
        payload={
            "document_id": str(document.id),
            "version": document.version,
            "file_count": len(assets),
        },
    )
    await db.commit()
    return await document_view(db, document)
