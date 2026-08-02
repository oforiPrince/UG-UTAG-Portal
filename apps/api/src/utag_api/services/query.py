import math
import re
import unicodedata
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.schemas.common import Page


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")
    return slug[:240] or "item"


async def unique_slug(
    db: AsyncSession,
    model: Any,
    title: str,
    requested: str | None = None,
) -> str:
    base = slugify(requested or title)
    candidate = base
    suffix = 2
    while await db.scalar(select(model.id).where(model.slug == candidate)) is not None:
        candidate = f"{base[:230]}-{suffix}"
        suffix += 1
    return candidate


async def paginate(
    db: AsyncSession,
    statement: Select[tuple[Any]],
    *,
    page: int,
    page_size: int,
) -> Page[Any]:
    total_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = int((await db.scalar(total_statement)) or 0)
    items = list(
        (await db.scalars(statement.offset((page - 1) * page_size).limit(page_size))).all()
    )
    return Page(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, math.ceil(total / page_size)),
    )
