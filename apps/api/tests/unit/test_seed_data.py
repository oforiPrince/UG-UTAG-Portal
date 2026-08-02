from sqlalchemy import func, select

from utag_api.models import AdPlan, AdSlot, FeatureFlag, OrganizationUnit, SiteSetting
from utag_api.seed_data import (
    AD_PLANS,
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
        assert await session.scalar(select(func.count()).select_from(AdPlan)) == len(AD_PLANS)

        active_keys = {
            row.key
            for row in (
                await session.scalars(select(AdSlot).where(AdSlot.is_active.is_(True)))
            ).all()
        }
        assert active_keys == {
            "home-after-hero",
            "news-sidebar",
            "events-sidebar",
            "content-inline",
            "footer",
        }
        footer = await session.scalar(select(AdSlot).where(AdSlot.key == "footer"))
        assert footer is not None
        assert footer.width == 970
        assert footer.height == 90
        assert footer.location.startswith("All public pages")
        plan = await session.scalar(select(AdPlan).where(AdPlan.name == "Site footer · 30 days"))
        assert plan is not None
        assert plan.slot_id == footer.id
