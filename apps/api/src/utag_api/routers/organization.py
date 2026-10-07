from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import delete, or_, select, update

from utag_api.database import new_id
from utag_api.dependencies import (
    DbSession,
    Principal,
    event_context,
    require_mutation_permissions,
    require_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import (
    Announcement,
    Conversation,
    ConversationInvite,
    ConversationMember,
    Document,
    Message,
    OrganizationUnit,
    User,
)
from utag_api.schemas.common import MessageResponse
from utag_api.schemas.domain import (
    OrganizationUnitCreate,
    OrganizationUnitUpdate,
    OrganizationUnitView,
)
from utag_api.services.deletion import (
    DeleteBlocker,
    audience_reference_count,
    block_delete_if_referenced,
    commit_permanent_delete,
    count_rows,
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
    if unit_type not in allowed_parents:
        raise ApiError(
            422,
            "parent_unit_invalid",
            f"A {unit_type} cannot have a parent unit",
        )
    if expected and parent.unit_type != expected:
        raise ApiError(
            422,
            "parent_unit_invalid",
            f"A {unit_type} must belong to a {expected}",
        )
    if not parent.is_active:
        raise ApiError(422, "parent_unit_invalid", "Select an active parent organization unit")
    return parent


async def ensure_deactivation_allowed(db: DbSession, item: OrganizationUnit) -> None:
    active_child = await db.scalar(
        select(OrganizationUnit.id)
        .where(
            OrganizationUnit.parent_id == item.id,
            OrganizationUnit.is_active.is_(True),
        )
        .limit(1)
    )
    if active_child is not None:
        raise ApiError(
            409,
            "organization_unit_in_use",
            "Move or deactivate this unit's active child units first",
        )
    linked_member = await db.scalar(
        select(User.id)
        .where(
            or_(
                User.college_id == item.id,
                User.school_id == item.id,
                User.department_id == item.id,
            )
        )
        .limit(1)
    )
    if linked_member is not None:
        raise ApiError(
            409,
            "organization_unit_in_use",
            "Reassign members linked to this organization unit before deactivating it",
        )


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
    elif changes.get("is_active") is True and item.parent_id is not None:
        parent = await validate_parent(db, item.unit_type, item.parent_id)
    if changes.get("is_active") is False and item.is_active:
        await ensure_deactivation_allowed(db, item)
    await validate_unit_identity(
        db,
        unit_type=item.unit_type,
        name=str(changes.get("name", item.name)),
        parent_id=changes.get("parent_id", item.parent_id),
        exclude_id=item.id,
    )
    for key, value in changes.items():
        setattr(item, key, value)
    if "parent_id" in changes and parent is not None:
        if item.unit_type == "school":
            await db.execute(
                update(User).where(User.school_id == item.id).values(college_id=parent.id)
            )
        if item.unit_type == "department":
            college = await db.get(OrganizationUnit, parent.parent_id)
            if college is None or college.unit_type != "college" or not college.is_active:
                raise ApiError(
                    422,
                    "parent_unit_invalid",
                    "The selected school must belong to an active college",
                )
            await db.execute(
                update(User)
                .where(User.department_id == item.id)
                .values(school_id=parent.id, college_id=college.id)
            )
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
    await ensure_deactivation_allowed(db, item)
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


@router.delete("/units/{unit_id}/permanent", response_model=MessageResponse)
async def delete_unit_permanently(
    unit_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[
        Principal,
        Depends(require_mutation_permissions("records.delete", "organization.manage")),
    ],
) -> MessageResponse:
    item = await db.get(OrganizationUnit, unit_id, with_for_update=True)
    if item is None:
        raise ApiError(404, "organization_unit_not_found", "Organization unit not found")

    announcement_audiences = list((await db.scalars(select(Announcement.audiences))).all())
    document_audiences = list((await db.scalars(select(Document.audiences))).all())
    member_count = await count_rows(
        db,
        User,
        or_(
            User.college_id == item.id,
            User.school_id == item.id,
            User.department_id == item.id,
        ),
    )
    child_count = await count_rows(
        db,
        OrganizationUnit,
        OrganizationUnit.parent_id == item.id,
    )

    system_group = None
    membership_count = 0
    message_count = 0
    invite_count = 0
    if item.unit_type in {"school", "department"}:
        system_group = await db.scalar(
            select(Conversation).where(
                Conversation.direct_key == f"system:{item.unit_type}:{item.id}"
            )
        )
        if system_group is not None:
            membership_count = await count_rows(
                db,
                ConversationMember,
                ConversationMember.conversation_id == system_group.id,
            )
            message_count = await count_rows(
                db,
                Message,
                Message.conversation_id == system_group.id,
            )
            invite_count = await count_rows(
                db,
                ConversationInvite,
                ConversationInvite.conversation_id == system_group.id,
            )

    block_delete_if_referenced(
        "organization unit",
        [
            DeleteBlocker("member affiliation", member_count),
            DeleteBlocker("child organization unit", child_count),
            DeleteBlocker(
                "announcement audience",
                audience_reference_count(
                    announcement_audiences,
                    item.id,
                    audience_type="unit",
                ),
            ),
            DeleteBlocker(
                "document audience",
                audience_reference_count(
                    document_audiences,
                    item.id,
                    audience_type="unit",
                ),
            ),
            DeleteBlocker("system chat membership", membership_count),
            DeleteBlocker("system chat message", message_count),
            DeleteBlocker("system chat invitation", invite_count),
        ],
        guidance=(
            "Reassign members, child units, audiences, and chat history first. "
            "Use Deactivate when the unit must remain available for historical records"
        ),
    )

    if system_group is not None:
        await db.execute(
            delete(ConversationInvite).where(ConversationInvite.conversation_id == system_group.id)
        )
        await db.delete(system_group)
    record_change(
        db,
        context=event_context(request, principal),
        action="organization.unit.deleted",
        resource_type="organization_unit",
        resource_id=item.id,
        topic="organization",
        payload={"unit_id": str(item.id), "unit_type": item.unit_type},
    )
    await db.delete(item)
    await commit_permanent_delete(db, "organization unit")
    return MessageResponse(message="Organization unit deleted permanently")
