from sqlalchemy import func, select

from utag_api.database import new_id
from utag_api.models import (
    AdPlan,
    AdSlot,
    Announcement,
    Conversation,
    ConversationMember,
    Document,
    FeatureFlag,
    OrganizationUnit,
    SiteSetting,
    User,
)
from utag_api.seed_data import (
    AD_PLANS,
    AD_SLOTS,
    CANONICAL_OFFICE_HOURS,
    FEATURE_FLAGS,
    ORGANIZATION_STRUCTURE,
    SITE_SETTINGS,
    organization_name_key,
    reconcile_office_hours,
    reconcile_organization,
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


def test_organization_name_key_normalizes_known_legacy_abbreviations() -> None:
    assert organization_name_key("UNIV. OF GHANA DENTAL SCHOOL") == organization_name_key(
        "University of Ghana Dental School"
    )
    assert organization_name_key("DEPT: RESTORATIVE DENTISTRY") == organization_name_key(
        "Department of Restorative Dentistry"
    )


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


async def test_portal_seed_preserves_administrator_created_advert_placements(
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    custom_id = new_id()
    async with session_factory() as session:
        session.add(
            AdSlot(
                id=custom_id,
                key="administrator-created-placement",
                name="Administrator-created placement",
                width=640,
                height=360,
                location="Special campaign page",
                is_active=True,
            )
        )
        await session.commit()

        await seed_portal_defaults(session)
        await seed_portal_defaults(session)

        custom = await session.get(AdSlot, custom_id)
        assert custom is not None
        assert custom.key == "administrator-created-placement"
        assert custom.is_active is True


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


async def test_organization_reconciliation_relinks_and_prunes_legacy_units(
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        await seed_portal_defaults(session)
        legacy_college = OrganizationUnit(
            id=new_id(),
            legacy_id=10,
            unit_type="school",
            name="COLLEGE OF HEALTH SCIENCES",
            slug="legacy-health-college",
            is_active=True,
        )
        legacy_school = OrganizationUnit(
            id=new_id(),
            legacy_id=11,
            unit_type="college",
            name="UNIV. OF GHANA DENTAL SCHOOL",
            slug="legacy-dental-school",
            parent_id=legacy_college.id,
            is_active=True,
        )
        legacy_department = OrganizationUnit(
            id=new_id(),
            legacy_id=12,
            unit_type="department",
            name="DEPT: RESTORATIVE DENTISTRY",
            slug="legacy-restorative-dentistry",
            parent_id=legacy_school.id,
            is_active=True,
        )
        unlinked_legacy = OrganizationUnit(
            id=new_id(),
            legacy_id=13,
            unit_type="department",
            name="Obsolete Legacy Department",
            slug="obsolete-legacy-department",
            is_active=True,
        )
        session.add_all([legacy_college, legacy_school, legacy_department, unlinked_legacy])
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert administrator is not None
        administrator.school_id = legacy_college.id
        administrator.college_id = legacy_school.id
        administrator.department_id = legacy_department.id
        document = Document(
            id=new_id(),
            public_id="legacy-affiliation-document",
            title="Dental School notice",
            category="internal",
            status="published",
            audiences=[{"type": "unit", "value": str(legacy_department.id)}],
            legal_hold=False,
            version=1,
        )
        announcement = Announcement(
            id=new_id(),
            title="Dental School announcement",
            content_json={},
            content_html="",
            status="published",
            priority="normal",
            audiences=[{"type": "unit", "value": str(legacy_school.id)}],
            version=1,
        )
        session.add_all([document, announcement])
        await session.flush()

        result = await reconcile_organization(session, prune_unlinked=True)
        await session.flush()

        canonical_college = await session.scalar(
            select(OrganizationUnit).where(
                OrganizationUnit.unit_type == "college",
                OrganizationUnit.name == "College of Health Sciences",
            )
        )
        canonical_school = await session.scalar(
            select(OrganizationUnit).where(
                OrganizationUnit.unit_type == "school",
                OrganizationUnit.name == "University of Ghana Dental School",
            )
        )
        canonical_department = await session.scalar(
            select(OrganizationUnit).where(
                OrganizationUnit.unit_type == "department",
                OrganizationUnit.name == "Department of Restorative Dentistry",
            )
        )
        assert canonical_college is not None
        assert canonical_school is not None
        assert canonical_department is not None
        assert canonical_school.parent_id == canonical_college.id
        assert canonical_department.parent_id == canonical_school.id
        assert administrator.college_id == canonical_college.id
        assert administrator.school_id == canonical_school.id
        assert administrator.department_id == canonical_department.id
        assert document.audiences == [{"type": "unit", "value": str(canonical_department.id)}]
        assert announcement.audiences == [{"type": "unit", "value": str(canonical_school.id)}]
        assert result.users_relinked == 1
        assert result.announcement_audiences_relinked == 1
        assert result.document_audiences_relinked == 1
        assert result.unresolved_users == 0
        assert result.legacy_units_pruned == 4
        assert await session.get(OrganizationUnit, legacy_department.id) is None
        assert await session.get(OrganizationUnit, unlinked_legacy.id) is None


async def test_organization_reconciliation_preserves_linked_unmatched_legacy_unit(
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        unmatched = OrganizationUnit(
            id=new_id(),
            legacy_id=99,
            unit_type="department",
            name="Unmapped Specialist Unit",
            slug="unmapped-specialist-unit",
            is_active=True,
        )
        custom = OrganizationUnit(
            id=new_id(),
            unit_type="department",
            name="Administrator-created Specialist Unit",
            slug="administrator-created-specialist-unit",
            is_active=True,
        )
        session.add_all([unmatched, custom])
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert administrator is not None
        administrator.department_id = unmatched.id
        await session.flush()

        result = await reconcile_organization(session, prune_unlinked=True)

        assert result.unresolved_users == 1
        assert result.legacy_units_retained == 1
        assert await session.get(OrganizationUnit, unmatched.id) is not None
        assert await session.get(OrganizationUnit, custom.id) is not None
        assert administrator.department_id == unmatched.id


async def test_organization_reconciliation_preserves_system_chat_history(
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert administrator is not None
        linked_unit = OrganizationUnit(
            id=new_id(),
            legacy_id=101,
            unit_type="department",
            name="Legacy Department with Chat History",
            slug="legacy-department-with-chat-history",
            is_active=True,
        )
        empty_unit = OrganizationUnit(
            id=new_id(),
            legacy_id=102,
            unit_type="department",
            name="Empty Legacy Chat Department",
            slug="empty-legacy-chat-department",
            is_active=True,
        )
        linked_group = Conversation(
            id=new_id(),
            kind="group",
            direct_key=f"system:department:{linked_unit.id}",
            title="Legacy Department with Chat History",
        )
        empty_group = Conversation(
            id=new_id(),
            kind="group",
            direct_key=f"system:department:{empty_unit.id}",
            title="Empty Legacy Chat Department",
        )
        session.add_all([linked_unit, empty_unit, linked_group, empty_group])
        await session.flush()
        session.add(
            ConversationMember(
                id=new_id(),
                conversation_id=linked_group.id,
                user_id=administrator.id,
                role="member",
            )
        )
        await session.flush()

        result = await reconcile_organization(session, prune_unlinked=True)
        await session.flush()

        assert result.legacy_units_retained == 1
        assert await session.get(OrganizationUnit, linked_unit.id) is not None
        assert await session.get(Conversation, linked_group.id) is not None
        assert await session.get(OrganizationUnit, empty_unit.id) is None
        assert await session.get(Conversation, empty_group.id) is None
