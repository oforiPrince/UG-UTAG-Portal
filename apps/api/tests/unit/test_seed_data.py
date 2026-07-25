from sqlalchemy import func, select

from utag_api.models import AdSlot, FeatureFlag, OrganizationUnit, SiteSetting
from utag_api.seed_data import (
    AD_SLOTS,
    FEATURE_FLAGS,
    ORGANIZATION_STRUCTURE,
    SITE_SETTINGS,
    seed_portal_defaults,
)


async def test_portal_seed_is_complete_and_idempotent(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        await seed_portal_defaults(session)
        await seed_portal_defaults(session)

        colleges = len(ORGANIZATION_STRUCTURE)
        schools = sum(len(rows) for rows in ORGANIZATION_STRUCTURE.values())
        departments = sum(
            len(departments)
            for rows in ORGANIZATION_STRUCTURE.values()
            for departments in rows.values()
        )
        assert (
            await session.scalar(select(func.count()).select_from(OrganizationUnit))
            == colleges + schools + departments
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(OrganizationUnit)
                .where(
                    OrganizationUnit.unit_type == "school",
                    OrganizationUnit.parent_id.is_not(None),
                )
            )
            == schools
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(OrganizationUnit)
                .where(
                    OrganizationUnit.unit_type == "department",
                    OrganizationUnit.parent_id.is_not(None),
                )
            )
            == departments
        )
        assert await session.scalar(select(func.count()).select_from(SiteSetting)) == len(
            SITE_SETTINGS
        )
        assert await session.scalar(select(func.count()).select_from(FeatureFlag)) == len(
            FEATURE_FLAGS
        )
        assert await session.scalar(select(func.count()).select_from(AdSlot)) == len(AD_SLOTS)
