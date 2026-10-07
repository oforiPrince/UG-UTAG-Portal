from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from utag_api.errors import ApiError


@dataclass(frozen=True, slots=True)
class DeleteBlocker:
    label: str
    count: int = 1
    plural_label: str | None = None

    @property
    def description(self) -> str:
        label = self.label if self.count == 1 else (self.plural_label or f"{self.label}s")
        return f"{self.count} {label}"


async def count_rows(
    db: AsyncSession,
    model: type[Any],
    *criteria: ColumnElement[bool],
) -> int:
    return int((await db.scalar(select(func.count()).select_from(model).where(*criteria))) or 0)


async def commit_permanent_delete(db: AsyncSession, resource: str) -> None:
    """Commit a hard delete while translating a concurrent FK race into a safe conflict."""
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(
            409,
            f"{resource.replace(' ', '_')}_delete_blocked",
            (
                f"Cannot delete this {resource} because another record is linked to it. "
                "Refresh the record, remove the dependency, and try again"
            ),
            details={
                "dependencies": [{"label": "linked record", "count": 1}],
                "guidance": "Refresh the record and remove the newly linked dependency first",
            },
        ) from exc


def block_delete_if_referenced(
    resource: str,
    blockers: Iterable[DeleteBlocker],
    *,
    guidance: str,
) -> None:
    found = [blocker for blocker in blockers if blocker.count > 0]
    if not found:
        return
    descriptions = [blocker.description for blocker in found]
    if len(descriptions) == 1:
        linked = descriptions[0]
    else:
        linked = f"{', '.join(descriptions[:-1])} and {descriptions[-1]}"
    raise ApiError(
        409,
        f"{resource.replace(' ', '_')}_delete_blocked",
        f"Cannot delete this {resource} because it is linked to {linked}. {guidance}",
        details={
            "dependencies": [
                {
                    "label": blocker.label,
                    "count": blocker.count,
                }
                for blocker in found
            ],
            "guidance": guidance,
        },
    )


def audience_reference_count(
    audience_lists: Sequence[list[dict[str, Any]] | None],
    target_id: object,
    *,
    audience_type: str,
) -> int:
    expected = str(target_id)
    return sum(
        1
        for audiences in audience_lists
        if any(
            audience.get("type") == audience_type and str(audience.get("value")) == expected
            for audience in (audiences or [])
        )
    )
