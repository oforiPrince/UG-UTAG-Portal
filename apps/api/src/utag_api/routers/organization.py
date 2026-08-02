from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from utag_api.database import new_id
from utag_api.dependencies import (
    DbSession,
    Principal,
    event_context,
    require_mutation_permissions,
    require_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import OrganizationUnit
from utag_api.schemas.common import MessageResponse
from utag_api.schemas.domain import (
    OrganizationUnitCreate,
    OrganizationUnitUpdate,
    OrganizationUnitView,
)
from utag_api.services.events import record_change
from utag_api.services.query import slugify

router = APIRouter(prefix="/organization", tags=["organization"])


def unit_view(
    item: OrganizationUnit, parent_names: dict[UUID, str] | None = None
) -> OrganizationUnitView:
    names = parent_names or {}
    return OrganizationUnitView.model_validate(
        {
            **{key: value for key, value in item.__dict__.items() if not key.startswith("_")},
            "parent_name": names.get(item.parent_id) if item.parent_id else None,
        }
    )


async def validate_parent(
    db: DbSession, unit_type: str, parent_id: UUID | None
) -> OrganizationUnit | None:
    allowed_parents = {"school": "college", "department": "school"}
    expected = allowed_parents.get(unit_type)
    if parent_id is None:
        if expected:
            raise ApiError(
                422,
                "parent_unit_invalid",
                f"A {unit_type} must belong to a {expected}",
            )
        return None
    parent = await db.get(OrganizationUnit, parent_id)
    if parent is None:
        raise ApiError(422, "parent_unit_invalid", "Parent organization unit not found")
    if unit_type == "college":
        raise ApiError(422, "parent_unit_invalid", "A college cannot have a parent unit")
    if expected and parent.unit_type != expected:
        raise ApiError(
            422,
            "parent_unit_invalid",
            f"A {unit_type} must belong to a {expected}",
        )
    return parent


async def validate_unit_identity(
    db: DbSession,
    *,
    unit_type: str,
    name: str,
    parent_id: UUID | None,
    exclude_id: UUID | None = None,
) -> None:
    statement = select(OrganizationUnit.id).where(
        OrganizationUnit.unit_type == unit_type,
        OrganizationUnit.name == name,
        (
            OrganizationUnit.parent_id.is_(None)
            if parent_id is None
            else OrganizationUnit.parent_id == parent_id
        ),
    )
    if exclude_id is not None:
        statement = statement.where(OrganizationUnit.id != exclude_id)
    if await db.scalar(statement.limit(1)) is not None:
        raise ApiError(
            409,
            "organization_unit_exists",
            "An organization unit with this name already exists under that parent",
        )


@router.get("/units", response_model=list[OrganizationUnitView])
async def units(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("dashboard.view"))],
    include_inactive: bool = False,
    unit_type: Annotated[
        str | None,
        Query(pattern="^(college|school|department|committee)$"),
    ] = None,
) -> list[OrganizationUnitView]:
    statement = select(OrganizationUnit).order_by(OrganizationUnit.unit_type, OrganizationUnit.name)
    if not include_inactive:
        statement = statement.where(OrganizationUnit.is_active.is_(True))
    if unit_type:
        statement = statement.where(OrganizationUnit.unit_type == unit_type)
    rows = list((await db.scalars(statement)).all())
    parent_ids = {item.parent_id for item in rows if item.parent_id is not None}
    parent_names = {
        item.id: item.name
        for item in (
            await db.scalars(select(OrganizationUnit).where(OrganizationUnit.id.in_(parent_ids)))
        ).all()
    }
    return [unit_view(item, parent_names) for item in rows]


@router.post("/units", response_model=OrganizationUnitView, status_code=201)
async def create_unit(
    payload: OrganizationUnitCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("organization.manage"))],
) -> OrganizationUnitView:
    parent = await validate_parent(db, payload.unit_type, payload.parent_id)
    await validate_unit_identity(
        db,
        unit_type=payload.unit_type,
        name=payload.name,
        parent_id=payload.parent_id,
    )
    base_slug = slugify(payload.name)
    slug = base_slug
    suffix = 2
    while await db.scalar(select(OrganizationUnit.id).where(OrganizationUnit.slug == slug)):
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    item = OrganizationUnit(
        id=new_id(),
        unit_type=payload.unit_type,
        name=payload.name,
        slug=slug,
        parent_id=payload.parent_id,
        is_active=payload.is_active,
    )
    db.add(item)
    record_change(
        db,
        context=event_context(request, principal),
        action="organization.unit.created",
        resource_type="organization_unit",
        resource_id=item.id,
        topic="organization",
        payload={"unit_id": str(item.id), "unit_type": item.unit_type},
    )
    await db.commit()
    return unit_view(item, {parent.id: parent.name} if parent else None)


@router.patch("/units/{unit_id}", response_model=OrganizationUnitView)
async def update_unit(
    unit_id: UUID,
    payload: OrganizationUnitUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("organization.manage"))],
) -> OrganizationUnitView:
    item = await db.get(OrganizationUnit, unit_id)
    if item is None:
        raise ApiError(404, "organization_unit_not_found", "Organization unit not found")
    changes = payload.model_dump(exclude_unset=True)
    parent: OrganizationUnit | None = None
    if "parent_id" in changes:
        if changes["parent_id"] == item.id:
            raise ApiError(422, "parent_unit_invalid", "A unit cannot be its own parent")
        parent = await validate_parent(db, item.unit_type, changes["parent_id"])
    await validate_unit_identity(
        db,
        unit_type=item.unit_type,
        name=str(changes.get("name", item.name)),
        parent_id=changes.get("parent_id", item.parent_id),
        exclude_id=item.id,
    )
    for key, value in changes.items():
        setattr(item, key, value)
    record_change(
        db,
        context=event_context(request, principal),
        action="organization.unit.updated",
        resource_type="organization_unit",
        resource_id=item.id,
        topic="organization",
        payload={"unit_id": str(item.id), "is_active": item.is_active},
        changes={key: {"to": str(value)} for key, value in changes.items()},
    )
    await db.commit()
    if parent is None and item.parent_id is not None:
        parent = await db.get(OrganizationUnit, item.parent_id)
    return unit_view(item, {parent.id: parent.name} if parent else None)


@router.delete("/units/{unit_id}", response_model=MessageResponse)
async def deactivate_unit(
    unit_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("organization.manage"))],
) -> MessageResponse:
    item = await db.get(OrganizationUnit, unit_id)
    if item is None:
        raise ApiError(404, "organization_unit_not_found", "Organization unit not found")
    item.is_active = False
    record_change(
        db,
        context=event_context(request, principal),
        action="organization.unit.deactivated",
        resource_type="organization_unit",
        resource_id=item.id,
        topic="organization",
        payload={"unit_id": str(item.id)},
    )
    await db.commit()
    return MessageResponse(message="Organization unit deactivated")
