import csv
import hashlib
import io
import math
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import ValidationError
from sqlalchemy import String, cast, delete, func, literal, or_, select, union_all
from starlette.responses import Response

from utag_api.database import new_id
from utag_api.dependencies import (
    CurrentPrincipal,
    DbSession,
    MutationPrincipal,
    Principal,
    event_context,
    require_mutation_permissions,
    require_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import Conversation, OrganizationUnit, Role, User
from utag_api.models.polls import Poll, PollDelivery, PollElectorate, PollOption
from utag_api.schemas.common import Page
from utag_api.schemas.polls import (
    AudienceOption,
    AudiencePreview,
    AudienceType,
    PollAudience,
    PollAudienceCount,
    PollCloseRequest,
    PollCreate,
    PollExtendRequest,
    PollReminderCount,
    PollResults,
    PollUpdate,
    PollView,
    PollVoteRequest,
)
from utag_api.services import polls
from utag_api.services.query import paginate

router = APIRouter(prefix="/polls", tags=["polls"])
PollManager = Annotated[Principal, Depends(require_mutation_permissions("polls.manage"))]
PollReader = Annotated[Principal, Depends(require_permissions("polls.manage"))]


async def authorized_poll(
    db: DbSession, poll_id: UUID, principal: Principal, *, lock: bool = False
) -> Poll:
    statement = select(Poll).where(Poll.id == poll_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    item = await db.scalar(statement)
    if item is None:
        raise ApiError(404, "poll_not_found", "Poll not found")
    manager = bool({"polls.manage", "polls.results", "polls.export"} & principal.permissions)
    if item.published_at is None:
        allowed = "polls.manage" in principal.permissions
    else:
        allowed = manager or await polls.eligible_member(db, item.id, principal.user.id)
    if not allowed:
        raise ApiError(404, "poll_not_found", "Poll not found")
    return item


def check_version(poll: Poll, if_match: str | None) -> None:
    if if_match is not None and if_match != f'"{poll.version}"':
        raise ApiError(412, "version_conflict", "Refresh this poll before saving")


def draft_only(poll: Poll) -> None:
    if poll.published_at is not None:
        raise ApiError(409, "poll_already_published", "Published ballot settings cannot be changed")


async def apply_configuration(db: DbSession, poll: Poll, configuration: PollCreate) -> None:
    values = configuration.model_dump(exclude={"options", "audiences"})
    for name, value in values.items():
        setattr(poll, name, value)
    poll.audiences = [item.model_dump(exclude_none=True) for item in configuration.audiences]
    await db.execute(delete(PollOption).where(PollOption.poll_id == poll.id))
    for position, label in enumerate(configuration.options):
        db.add(PollOption(id=new_id(), poll_id=poll.id, label=label, position=position))


@router.get("", response_model=Page[PollView])
async def list_polls(
    db: DbSession,
    principal: CurrentPrincipal,
    q: str | None = Query(default=None, max_length=150),
    state: Literal["all", "draft", "scheduled", "open", "closed"] = "all",
    eligible_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[PollView]:
    now = datetime.now(UTC)
    statement = select(Poll)
    manager = bool({"polls.manage", "polls.results", "polls.export"} & principal.permissions)
    if not manager or eligible_only:
        statement = statement.where(
            Poll.published_at.is_not(None),
            Poll.id.in_(
                select(PollElectorate.poll_id).where(PollElectorate.user_id == principal.user.id)
            ),
        )
    elif "polls.manage" not in principal.permissions:
        statement = statement.where(Poll.published_at.is_not(None))
    if q:
        statement = statement.where(or_(Poll.title.ilike(f"%{q}%"), Poll.question.ilike(f"%{q}%")))
    if state == "draft":
        statement = statement.where(Poll.published_at.is_(None))
    elif state == "closed":
        statement = statement.where(
            Poll.published_at.is_not(None),
            or_(Poll.closed_at.is_not(None), Poll.closes_at <= now),
        )
    elif state in {"open", "scheduled"}:
        statement = statement.where(
            Poll.published_at.is_not(None), Poll.closed_at.is_(None), Poll.closes_at > now
        )
        statement = statement.where(
            Poll.opens_at > now
            if state == "scheduled"
            else or_(Poll.opens_at.is_(None), Poll.opens_at <= now)
        )
    result = await paginate(
        db, statement.order_by(Poll.created_at.desc()), page=page, page_size=page_size
    )
    return Page(
        items=await polls.poll_views(db, result.items, principal),
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        pages=result.pages,
    )


@router.get("/audiences", response_model=Page[AudienceOption])
async def audience_options(
    db: DbSession,
    principal: PollReader,
    type: AudienceType | None = None,
    q: str | None = Query(default=None, max_length=150),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[AudienceOption]:
    choices = []
    if type in {None, "all_members"}:
        everyone = select(
            literal("all_members").label("type"),
            literal("all").label("value"),
            literal("All active members").label("label"),
        )
        if q:
            everyone = everyone.where(literal("All active members").ilike(f"%{q}%"))
        choices.append(everyone)
    if type in {None, "college", "school", "department"}:
        units = select(
            OrganizationUnit.unit_type.label("type"),
            cast(OrganizationUnit.id, String).label("value"),
            OrganizationUnit.name.label("label"),
        ).where(
            OrganizationUnit.is_active.is_(True),
            OrganizationUnit.unit_type.in_([type] if type else ["college", "school", "department"]),
        )
        if q:
            units = units.where(OrganizationUnit.name.ilike(f"%{q}%"))
        choices.append(units)
    if type in {None, "role"}:
        roles = select(
            literal("role").label("type"), Role.key.label("value"), Role.name.label("label")
        )
        if q:
            roles = roles.where(or_(Role.name.ilike(f"%{q}%"), Role.key.ilike(f"%{q}%")))
        choices.append(roles)
    if type in {None, "chat_group"}:
        groups = select(
            literal("chat_group").label("type"),
            cast(Conversation.id, String).label("value"),
            func.coalesce(Conversation.title, "Untitled group").label("label"),
        ).where(Conversation.kind == "group", Conversation.is_archived.is_(False))
        if q:
            groups = groups.where(Conversation.title.ilike(f"%{q}%"))
        choices.append(groups)
    if type in {None, "member"}:
        name = func.trim(User.title + " " + User.other_name + " " + User.surname)
        members = select(
            literal("member").label("type"),
            cast(User.id, String).label("value"),
            name.label("label"),
        ).where(User.status == "active")
        if q:
            members = members.where(or_(name.ilike(f"%{q}%"), User.staff_id.ilike(f"%{q}%")))
        choices.append(members)
    combined = union_all(*choices).subquery()
    total = int(await db.scalar(select(func.count()).select_from(combined)) or 0)
    rows = (
        await db.execute(
            select(combined)
            .order_by(combined.c.label, combined.c.type, combined.c.value)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    # SQLite casts UUIDs as hex; normalize to the same UUID strings returned by views.
    return Page(
        items=[
            AudienceOption.model_validate(
                {
                    "type": kind,
                    "value": str(UUID(value)) if kind not in {"all_members", "role"} else value,
                    "label": label,
                }
            )
            for kind, value, label in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.post("/audience-preview", response_model=PollAudienceCount)
async def audience_preview(
    payload: AudiencePreview, db: DbSession, principal: PollManager
) -> PollAudienceCount:
    return PollAudienceCount(
        eligible_count=len(await polls.resolve_audience_ids(db, payload.audiences))
    )


@router.post("", response_model=PollView, status_code=201)
async def create_poll(
    payload: PollCreate, request: Request, db: DbSession, principal: PollManager
) -> PollView:
    await polls.resolve_audience_ids(db, payload.audiences)
    poll = Poll(id=new_id(), created_by_id=principal.user.id, version=1)
    db.add(poll)
    # Configure before flushing the required title/question columns.
    for name, value in payload.model_dump(exclude={"options", "audiences"}).items():
        setattr(poll, name, value)
    poll.audiences = [item.model_dump(exclude_none=True) for item in payload.audiences]
    await db.flush()
    for position, label in enumerate(payload.options):
        db.add(PollOption(id=new_id(), poll_id=poll.id, label=label, position=position))
    polls.emit_poll_change(db, poll, event_context(request, principal), "poll.created")
    await db.commit()
    return await polls.poll_view(db, poll, principal)


@router.get("/{poll_id}", response_model=PollView)
async def get_poll(
    poll_id: UUID, db: DbSession, principal: CurrentPrincipal, response: Response
) -> PollView:
    poll = await authorized_poll(db, poll_id, principal)
    response.headers["ETag"] = f'"{poll.version}"'
    return await polls.poll_view(db, poll, principal)


@router.patch("/{poll_id}", response_model=PollView)
async def update_poll(
    poll_id: UUID,
    payload: PollUpdate,
    request: Request,
    db: DbSession,
    principal: PollManager,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> PollView:
    poll = await authorized_poll(db, poll_id, principal, lock=True)
    draft_only(poll)
    check_version(poll, if_match)
    old_options = await polls.poll_options(db, poll.id)
    configuration = {
        name: getattr(poll, name) for name in PollCreate.model_fields if name != "options"
    }
    # SQLite strips timezone metadata from stored timestamps. Normalize only
    # inherited dates; explicit client dates still pass the strict validator.
    for name in ("opens_at", "closes_at"):
        if configuration[name] is not None:
            configuration[name] = polls.utc(configuration[name])
    configuration["options"] = [item.label for item in old_options]
    configuration.update(payload.model_dump(exclude_unset=True))
    try:
        validated = PollCreate.model_validate(configuration)
    except ValidationError as exc:
        raise ApiError(
            422,
            "invalid_poll_configuration",
            "Review the poll settings",
            details=[{"message": error["msg"]} for error in exc.errors()],
        ) from None
    await polls.resolve_audience_ids(db, validated.audiences)
    await apply_configuration(db, poll, validated)
    poll.version += 1
    polls.emit_poll_change(db, poll, event_context(request, principal), "poll.updated")
    await db.commit()
    return await polls.poll_view(db, poll, principal)


@router.post("/{poll_id}/publish", response_model=PollView)
async def publish_poll(
    poll_id: UUID, request: Request, db: DbSession, principal: PollManager
) -> PollView:
    poll = await authorized_poll(db, poll_id, principal, lock=True)
    if poll.published_at is not None:
        return await polls.poll_view(db, poll, principal)
    now = datetime.now(UTC)
    opens_at = polls.utc(poll.opens_at) if poll.opens_at else now
    if poll.closes_at is None or polls.utc(poll.closes_at) <= max(now, opens_at):
        raise ApiError(
            422,
            "invalid_poll_schedule",
            "Set a closing time after the poll opens and after the current time",
        )
    recipient_ids = await polls.resolve_audience_ids(
        db, [PollAudience.model_validate(item) for item in poll.audiences]
    )
    if not recipient_ids:
        raise ApiError(422, "empty_poll_audience", "This audience has no active members")
    poll.opens_at = opens_at
    poll.published_at = now
    poll.version += 1
    for user_id in recipient_ids:
        db.add(PollElectorate(poll_id=poll.id, user_id=user_id))
    await db.flush()
    polls.emit_poll_change(db, poll, event_context(request, principal), "poll.published")
    await polls.emit_electorate_change(db, poll, "poll.published")
    await polls.reconcile_one_poll(db, poll)
    await db.commit()
    return await polls.poll_view(db, poll, principal)


@router.post("/{poll_id}/duplicate", response_model=PollView, status_code=201)
async def duplicate_poll(
    poll_id: UUID, request: Request, db: DbSession, principal: PollManager
) -> PollView:
    original = await authorized_poll(db, poll_id, principal, lock=True)
    values = {
        name: getattr(original, name)
        for name in PollCreate.model_fields
        if name not in {"options", "opens_at", "closes_at"}
    }
    values["title"] = f"{original.title[:243]} (copy)"
    values["options"] = [item.label for item in await polls.poll_options(db, original.id)]
    return await create_poll(PollCreate.model_validate(values), request, db, principal)


@router.put("/{poll_id}/vote", response_model=PollView)
async def vote(
    poll_id: UUID,
    payload: PollVoteRequest,
    request: Request,
    db: DbSession,
    principal: MutationPrincipal,
) -> PollView:
    poll = await authorized_poll(db, poll_id, principal, lock=True)
    await polls.cast_vote(
        db, poll, principal, payload.option_ids, event_context(request, principal)
    )
    await db.commit()
    return await polls.poll_view(db, poll, principal)


@router.get("/{poll_id}/results", response_model=PollResults)
async def get_results(poll_id: UUID, db: DbSession, principal: CurrentPrincipal) -> PollResults:
    poll = await authorized_poll(db, poll_id, principal)
    return await polls.results_view(db, poll, principal)


@router.get("/{poll_id}/reminders/preview", response_model=PollReminderCount)
async def reminder_preview(
    poll_id: UUID, db: DbSession, principal: PollReader
) -> PollReminderCount:
    poll = await authorized_poll(db, poll_id, principal)
    return PollReminderCount(recipient_count=len(await polls.nonvoter_ids(db, poll)))


@router.post("/{poll_id}/reminders", response_model=PollReminderCount)
async def send_reminders(
    poll_id: UUID,
    request: Request,
    db: DbSession,
    principal: PollManager,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=150)
    ] = None,
) -> PollReminderCount:
    poll = await authorized_poll(db, poll_id, principal, lock=True)
    recipients = await polls.nonvoter_ids(db, poll)
    key = idempotency_key or str(new_id())
    campaign = f"reminder:{hashlib.sha256(key.encode()).hexdigest()}"
    existing = int(
        await db.scalar(
            select(func.count(PollDelivery.id)).where(
                PollDelivery.poll_id == poll.id, PollDelivery.campaign == campaign
            )
        )
        or 0
    )
    if existing:
        return PollReminderCount(recipient_count=existing)
    count = await polls.deliver_poll_notifications(
        db,
        poll,
        recipients,
        campaign,
        title=f"Your vote is still needed: {poll.title}",
        context=event_context(request, principal),
    )
    polls.emit_poll_change(db, poll, event_context(request, principal), "poll.reminders.sent")
    await db.commit()
    return PollReminderCount(recipient_count=count)


@router.post("/{poll_id}/extend", response_model=PollView)
async def extend_poll(
    poll_id: UUID,
    payload: PollExtendRequest,
    request: Request,
    db: DbSession,
    principal: PollManager,
) -> PollView:
    poll = await authorized_poll(db, poll_id, principal, lock=True)
    if polls.poll_state(poll) not in {"open", "scheduled"} or poll.closes_at is None:
        raise ApiError(
            409, "poll_extension_unavailable", "Only an active or scheduled poll can be extended"
        )
    if payload.closes_at <= polls.utc(poll.closes_at):
        raise ApiError(
            422, "invalid_poll_extension", "Choose a closing time after the current deadline"
        )
    old_deadline = polls.utc(poll.closes_at).isoformat()
    poll.closes_at = payload.closes_at
    poll.version += 1
    polls.emit_poll_change(
        db,
        poll,
        event_context(request, principal),
        "poll.extended",
        reason=payload.reason,
        changes={"previous_closes_at": old_deadline, "closes_at": payload.closes_at.isoformat()},
    )
    await polls.emit_electorate_change(db, poll, "poll.extended")
    await polls.deliver_poll_notifications(
        db,
        poll,
        await polls.active_recipient_ids(db, poll.id),
        f"extension:{poll.version}",
        title=f"Voting deadline extended: {poll.title}",
        context=event_context(request, principal),
    )
    await db.commit()
    return await polls.poll_view(db, poll, principal)


@router.post("/{poll_id}/close", response_model=PollView)
async def close_poll(
    poll_id: UUID,
    payload: PollCloseRequest,
    request: Request,
    db: DbSession,
    principal: PollManager,
) -> PollView:
    poll = await authorized_poll(db, poll_id, principal, lock=True)
    if poll.published_at is None:
        raise ApiError(409, "poll_not_published", "Publish the poll before closing it")
    if polls.poll_state(poll) == "closed":
        return await polls.poll_view(db, poll, principal)
    if polls.poll_state(poll) != "open":
        raise ApiError(409, "poll_not_open", "Only an open poll can be closed early")
    poll.closed_at = datetime.now(UTC)
    poll.version += 1
    polls.emit_poll_change(
        db, poll, event_context(request, principal), "poll.closed_early", reason=payload.reason
    )
    await polls.reconcile_one_poll(db, poll)
    await db.commit()
    return await polls.poll_view(db, poll, principal)


def csv_cell(value: str) -> str:
    # Protect spreadsheet consumers from formula execution in member-supplied labels.
    return f"'{value}" if value.lstrip().startswith(("=", "+", "-", "@")) else value


@router.get("/{poll_id}/export")
async def export_poll(
    poll_id: UUID,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("polls.export"))],
) -> Response:
    poll = await authorized_poll(db, poll_id, principal)
    results = await polls.results_view(db, poll, principal)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Poll", csv_cell(poll.title)])
    writer.writerow(["Question", csv_cell(poll.question)])
    writer.writerow(["Generated at (UTC)", results.generated_at.isoformat()])
    writer.writerow(["Eligible members", results.eligible_count])
    writer.writerow(["Responses", results.response_count])
    writer.writerow(["Turnout (%)", results.turnout_percent])
    writer.writerow([])
    writer.writerow(["Option", "Votes", "Percent of respondents"])
    for option in results.options:
        writer.writerow([csv_cell(option.label), option.votes, option.percent])
    if results.named_voters is not None:
        writer.writerow([])
        writer.writerow(["Member", "Selected options"])
        for member in results.named_voters:
            writer.writerow(
                [csv_cell(member.member_name), csv_cell("; ".join(member.option_labels))]
            )
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="poll-{poll.id}.csv"'},
    )
