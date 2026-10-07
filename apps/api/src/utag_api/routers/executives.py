import csv
import io
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
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
from utag_api.models import ExecutiveAppointment, User
from utag_api.schemas.common import MessageResponse, Page
from utag_api.schemas.domain import ExecutiveCreate, ExecutiveView
from utag_api.services.content import sanitize_html
from utag_api.services.deletion import commit_permanent_delete
from utag_api.services.events import record_change
from utag_api.services.executives import executive_row_order_key
from utag_api.services.identity import require_public_profile_image
from utag_api.services.query import paginate_sequence

router = APIRouter(prefix="/executives", tags=["executives"])


def view(appointment: ExecutiveAppointment, user: User) -> ExecutiveView:
    return ExecutiveView(
        **{key: value for key, value in appointment.__dict__.items() if not key.startswith("_")},
        full_name=user.full_name,
        title=user.title,
        academic_rank=user.academic_rank,
        profile_media_id=user.profile_media_id,
    )


@router.get("", response_model=Page[ExecutiveView])
async def list_executives(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("members.view"))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    q: str | None = None,
    include_past: bool = True,
    is_active: bool | None = None,
    sort_by: str | None = None,
    sort_dir: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
) -> Page[ExecutiveView]:
    del principal
    statement = select(ExecutiveAppointment, User).join(
        User, User.id == ExecutiveAppointment.user_id
    )
    if is_active is not None:
        statement = statement.where(ExecutiveAppointment.is_active.is_(is_active))
    elif not include_past:
        statement = statement.where(ExecutiveAppointment.is_active.is_(True))
    rows = sorted(
        (await db.execute(statement)).all(),
        key=lambda row: executive_row_order_key(row[0], row[1]),
    )
    items = [view(appointment, user) for appointment, user in rows]
    if q and q.strip():
        needle = q.strip().casefold()
        items = [
            item
            for item in items
            if needle
            in " ".join(
                part
                for part in (
                    item.full_name,
                    item.position,
                    item.portfolio or "",
                    item.title,
                )
                if part
            ).casefold()
        ]
    sortable = {"full_name", "position", "is_active"}
    if sort_by in sortable:
        reverse = sort_dir == "desc"
        items = sorted(
            items,
            key=lambda item: (getattr(item, sort_by), item.full_name.casefold()),
            reverse=reverse,
        )
    return paginate_sequence(items, page=page, page_size=page_size)


@router.get("/{appointment_id:uuid}", response_model=ExecutiveView)
async def get_executive(
    appointment_id: UUID,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("members.view"))],
) -> ExecutiveView:
    del principal
    row = (
        await db.execute(
            select(ExecutiveAppointment, User)
            .join(User, User.id == ExecutiveAppointment.user_id)
            .where(ExecutiveAppointment.id == appointment_id)
        )
    ).one_or_none()
    if row is None:
        raise ApiError(404, "executive_not_found", "Executive appointment not found")
    appointment, user = row
    return view(appointment, user)


@router.get("/exports/csv")
async def export_executives(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("members.export"))],
) -> StreamingResponse:
    rows = sorted(
        (
            await db.execute(
                select(ExecutiveAppointment, User).join(
                    User, User.id == ExecutiveAppointment.user_id
                )
            )
        ).all(),
        key=lambda row: executive_row_order_key(row[0], row[1]),
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "name",
            "email",
            "position",
            "portfolio",
            "appointed_on",
            "ended_on",
            "term_number",
            "acting",
            "current",
            "public",
            "show_email",
            "show_phone",
        ]
    )
    for appointment, user in rows:
        writer.writerow(
            [
                user.full_name,
                user.email,
                appointment.position,
                appointment.portfolio or "",
                appointment.appointed_on or "",
                appointment.ended_on or "",
                appointment.term_number,
                appointment.is_acting,
                appointment.is_active,
                appointment.is_public,
                appointment.show_email,
                appointment.show_phone,
            ]
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ug-utag-executives.csv"},
    )


@router.post("", response_model=ExecutiveView, status_code=201)
async def create_executive(
    payload: ExecutiveCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("executives.manage"))],
) -> ExecutiveView:
    user = await db.get(User, payload.user_id)
    if user is None:
        raise ApiError(404, "member_not_found", "Member not found")
    await require_public_profile_image(db, payload.profile_media_id)
    data = payload.model_dump()
    data.pop("profile_media_id")
    data["biography_html"] = sanitize_html(payload.biography_html)
    user.profile_media_id = payload.profile_media_id
    appointment = ExecutiveAppointment(id=new_id(), **data)
    db.add(appointment)
    record_change(
        db,
        context=event_context(request, principal),
        action="executive.created",
        resource_type="executive_appointment",
        resource_id=appointment.id,
        topic="executives",
        payload={"appointment_id": str(appointment.id), "user_id": str(user.id)},
    )
    await db.commit()
    return view(appointment, user)


@router.patch("/{appointment_id}", response_model=ExecutiveView)
async def update_executive(
    appointment_id: UUID,
    payload: ExecutiveCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("executives.manage"))],
) -> ExecutiveView:
    appointment = await db.get(ExecutiveAppointment, appointment_id)
    if appointment is None:
        raise ApiError(404, "executive_not_found", "Executive appointment not found")
    user = await db.get(User, payload.user_id)
    if user is None:
        raise ApiError(409, "member_missing", "The linked member no longer exists")
    await require_public_profile_image(db, payload.profile_media_id)
    data = payload.model_dump()
    data.pop("profile_media_id")
    data["biography_html"] = sanitize_html(payload.biography_html)
    for key, value in data.items():
        setattr(appointment, key, value)
    user.profile_media_id = payload.profile_media_id
    record_change(
        db,
        context=event_context(request, principal),
        action="executive.updated",
        resource_type="executive_appointment",
        resource_id=appointment.id,
        topic="executives",
        payload={"appointment_id": str(appointment.id), "is_active": appointment.is_active},
    )
    await db.commit()
    return view(appointment, user)


@router.delete("/{appointment_id}", response_model=MessageResponse)
async def end_executive_appointment(
    appointment_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("executives.manage"))],
) -> MessageResponse:
    appointment = await db.get(ExecutiveAppointment, appointment_id)
    if appointment is None:
        raise ApiError(404, "executive_not_found", "Executive appointment not found")
    appointment.is_active = False
    appointment.ended_on = appointment.ended_on or datetime.now(UTC).date()
    record_change(
        db,
        context=event_context(request, principal),
        action="executive.ended",
        resource_type="executive_appointment",
        resource_id=appointment.id,
        topic="executives",
        payload={"appointment_id": str(appointment.id), "is_active": False},
    )
    await db.commit()
    return MessageResponse(message="Executive appointment ended")


@router.delete("/{appointment_id}/permanent", response_model=MessageResponse)
async def delete_executive_appointment_permanently(
    appointment_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[
        Principal,
        Depends(require_mutation_permissions("records.delete", "executives.manage")),
    ],
) -> MessageResponse:
    appointment = await db.get(ExecutiveAppointment, appointment_id, with_for_update=True)
    if appointment is None:
        raise ApiError(404, "executive_not_found", "Executive appointment not found")
    record_change(
        db,
        context=event_context(request, principal),
        action="executive.deleted",
        resource_type="executive_appointment",
        resource_id=appointment.id,
        topic="executives",
        payload={
            "appointment_id": str(appointment.id),
            "user_id": str(appointment.user_id),
        },
        reason="Administrator permanently deleted an executive appointment",
    )
    await db.delete(appointment)
    await commit_permanent_delete(db, "executive appointment")
    return MessageResponse(message="Executive appointment deleted permanently")
