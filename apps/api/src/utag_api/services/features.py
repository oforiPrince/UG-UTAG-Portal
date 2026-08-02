from collections.abc import Awaitable, Callable

from sqlalchemy import select

from utag_api.dependencies import DbSession
from utag_api.errors import ApiError
from utag_api.models import FeatureFlag


async def feature_enabled(db: DbSession, key: str, *, default: bool = True) -> bool:
    enabled = await db.scalar(select(FeatureFlag.enabled).where(FeatureFlag.key == key))
    return default if enabled is None else bool(enabled)


def feature_required(key: str) -> Callable[[DbSession], Awaitable[None]]:
    async def require_enabled(db: DbSession) -> None:
        if not await feature_enabled(db, key):
            raise ApiError(404, "feature_disabled", "This feature is not available")

    return require_enabled
