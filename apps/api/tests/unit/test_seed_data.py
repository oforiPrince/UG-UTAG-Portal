from sqlalchemy import func, select

from utag_api.database import new_id
from utag_api.models import AdPlan, AdSlot, FeatureFlag, OrganizationUnit, SiteSetting
from utag_api.seed_data import (
    AD_PLANS,
    AD_SLOTS,
    CANONICAL_OFFICE_HOURS,
    FEATURE_FLAGS,
    ORGANIZATION_STRUCTURE,
    SITE_SETTINGS,
    reconcile_office_hours,
    seed_portal_defaults,
)


def test_reconcile_office_hours_rewrites_stale_six_pm() -> None:
    updated = reconcile_office_hours(
        {
            "email": "utagoffice@ug.edu.gh",
            "phone": "+233 (0) 24 427 7275",
            "office_hours": "Monday-Friday, 9:00 AM-6:00 PM",
        }
    )
    assert updated["office_hours"] == CANONICAL_OFFICE_HOURS
    assert updated["email"] == "utagoffice@ug.edu.gh"


def test_reconcile_office_hours_leaves_current_value_alone() -> None:
    current = {
        "email": "utagoffice@ug.edu.gh",
        "office_hours": CANONICAL_OFFICE_HOURS,
    }
    assert reconcile_office_hours(current) is current


async def test_seed_rewrites_stale_office_hours_on_existing_contact(
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        session.add(
            SiteSetting(
                id=new_id(),
                key="site.contact",
                value={
                    "email": "utagoffice@ug.edu.gh",
                    "phone": "+233 (0) 24 427 7275",
                    "address": "University of Ghana, Legon, Accra",
                    "office_hours": "Monday-Friday, 9:00 AM-6:00 PM",
                },
                is_public=True,
            )
        )
        await session.flush()

        await seed_portal_defaults(session)
        await session.flush()

        contact = await session.scalar(
            select(SiteSetting).where(SiteSetting.key == "site.contact")
        )
        assert contact is not None
        assert contact.value["office_hours"] == CANONICAL_OFFICE_HOURS
        assert contact.value["email"] == "utagoffice@ug.edu.gh"


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

        contact = await session.scalar(
            select(SiteSetting).where(SiteSetting.key == "site.contact")
        )
        assert contact is not None
        assert contact.value["office_hours"] == CANONICAL_OFFICE_HOURS
