from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.database import new_id
from utag_api.models import ExecutiveAppointment, OrganizationUnit, Role, User, UserRole
from utag_api.security import hash_password, verify_password
from utag_api.seed_data import seed_portal_defaults
from utag_api.services.identity import seed_authorization


@dataclass(frozen=True, slots=True)
class DemoAccount:
    email: str
    staff_id: str
    title: str
    other_name: str
    surname: str
    gender: str
    academic_rank: str
    roles: tuple[str, ...]
    executive_position: str | None = None
    portfolio: str | None = None


DEMO_ACCOUNTS = (
    DemoAccount(
        "demo.member@utag.com",
        "DEMO-001",
        "Mr.",
        "Kofi",
        "Mensah",
        "Male",
        "Assistant Lecturer",
        ("member",),
    ),
    DemoAccount(
        "demo.executive@utag.com",
        "DEMO-002",
        "Dr.",
        "Ama",
        "Owusu",
        "Female",
        "Senior Lecturer",
        ("executive",),
        "President",
        "Branch leadership and member representation",
    ),
    DemoAccount(
        "demo.editor@utag.com",
        "DEMO-003",
        "Dr.",
        "Efua",
        "Boateng",
        "Female",
        "Lecturer",
        ("editor",),
    ),
    DemoAccount(
        "demo.publisher@utag.com",
        "DEMO-004",
        "Prof.",
        "Kojo",
        "Asare",
        "Male",
        "Professor",
        ("publisher",),
    ),
    DemoAccount(
        "demo.secretary@utag.com",
        "DEMO-005",
        "Dr.",
        "Akosua",
        "Nyarko",
        "Female",
        "Senior Lecturer",
        ("secretary",),
        "Secretary",
        "Secretariat, records and branch correspondence",
    ),
    DemoAccount(
        "demo.administrator@utag.com",
        "DEMO-006",
        "Dr.",
        "Kwame",
        "Ofori",
        "Male",
        "Associate Professor",
        ("administrator",),
    ),
    DemoAccount(
        "demo.vice-president@utag.com",
        "DEMO-007",
        "Dr.",
        "Yaw",
        "Addo",
        "Male",
        "Senior Lecturer",
        ("executive",),
        "Vice President",
        "Deputy branch leadership and coordination",
    ),
    DemoAccount(
        "demo.assistant-secretary@utag.com",
        "DEMO-008",
        "Ms.",
        "Abena",
        "Sarpong",
        "Female",
        "Lecturer",
        ("executive",),
        "Assistant Secretary",
        "Secretariat support and member communications",
    ),
    DemoAccount(
        "demo.treasurer@utag.com",
        "DEMO-009",
        "Dr.",
        "Nana",
        "Opoku",
        "Male",
        "Senior Lecturer",
        ("executive",),
        "Treasurer",
        "Finance, reporting and stewardship",
    ),
    DemoAccount(
        "demo.assistant-treasurer@utag.com",
        "DEMO-010",
        "Dr.",
        "Esi",
        "Quartey",
        "Female",
        "Lecturer",
        ("executive",),
        "Assistant Treasurer",
        "Financial administration support",
    ),
    DemoAccount(
        "demo.organiser@utag.com",
        "DEMO-011",
        "Mr.",
        "Kweku",
        "Aidoo",
        "Male",
        "Assistant Lecturer",
        ("executive",),
        "Organiser",
        "Member mobilisation and events",
    ),
    DemoAccount(
        "demo.womens-officer@utag.com",
        "DEMO-012",
        "Dr.",
        "Adwoa",
        "Bediako",
        "Female",
        "Senior Lecturer",
        ("executive",),
        "Women's Executive Officer",
        "Gender equity and women members' welfare",
    ),
    DemoAccount(
        "demo.past-president@utag.com",
        "DEMO-013",
        "Prof.",
        "Fiifi",
        "Ansah",
        "Male",
        "Professor",
        ("executive",),
        "Past President",
        "Institutional memory and advisory support",
    ),
    DemoAccount(
        "demo.national-president@utag.com",
        "DEMO-014",
        "Prof.",
        "Naa",
        "Tetteh",
        "Female",
        "Professor",
        ("executive",),
        "National President",
        "National association liaison",
    ),
    DemoAccount(
        "demo.cbas-rep@utag.com",
        "DEMO-015",
        "Dr.",
        "Josephine",
        "Yeboah",
        "Female",
        "Senior Lecturer",
        ("executive",),
        "CBAS Rep",
        "College of Basic and Applied Sciences representation",
    ),
    DemoAccount(
        "demo.chs-rep@utag.com",
        "DEMO-016",
        "Dr.",
        "Daniel",
        "Acquah",
        "Male",
        "Senior Lecturer",
        ("executive",),
        "CHS Rep",
        "College of Health Sciences representation",
    ),
    DemoAccount(
        "demo.coe-rep@utag.com",
        "DEMO-017",
        "Dr.",
        "Mabel",
        "Lartey",
        "Female",
        "Lecturer",
        ("executive",),
        "COE Rep",
        "College of Education representation",
    ),
    DemoAccount(
        "demo.coh-rep@utag.com",
        "DEMO-018",
        "Dr.",
        "Samuel",
        "Amartey",
        "Male",
        "Senior Lecturer",
        ("executive",),
        "COH Rep",
        "College of Humanities representation",
    ),
)


@dataclass(frozen=True, slots=True)
class DemoSeedResult:
    accounts: int
    executive_appointments: int


async def seed_demo_data(db: AsyncSession, password: str) -> DemoSeedResult:
    """Create or refresh the named development-only role and executive accounts."""

    await seed_authorization(db)
    await seed_portal_defaults(db)

    roles = {row.key: row for row in (await db.scalars(select(Role))).all()}
    units = (await db.scalars(select(OrganizationUnit))).all()
    units_by_id = {unit.id: unit for unit in units}
    organization_paths: list[tuple[OrganizationUnit, OrganizationUnit, OrganizationUnit]] = []
    for department in sorted(
        (unit for unit in units if unit.unit_type == "department"),
        key=lambda unit: unit.name,
    ):
        school = units_by_id.get(department.parent_id) if department.parent_id else None
        college = units_by_id.get(school.parent_id) if school and school.parent_id else None
        if school and college:
            organization_paths.append((college, school, department))
    if not organization_paths:
        raise RuntimeError("Demo accounts require seeded college, school, and department lookups")

    existing_users = {
        row.email: row
        for row in (
            await db.scalars(
                select(User).where(User.email.in_([row.email for row in DEMO_ACCOUNTS]))
            )
        ).all()
    }
    users_by_email: dict[str, User] = {}
    for index, account in enumerate(DEMO_ACCOUNTS):
        college, school, department = organization_paths[index % len(organization_paths)]
        user = existing_users.get(account.email)
        if user is None:
            user = User(
                id=new_id(),
                email=account.email,
                password_hash=hash_password(password),
                other_name=account.other_name,
                surname=account.surname,
            )
            db.add(user)
        else:
            password_matches, _ = verify_password(user.password_hash, password)
            if not password_matches:
                user.password_hash = hash_password(password)
        user.staff_id = account.staff_id
        user.must_change_password = False
        user.email_verified = True
        user.status = "active"
        user.title = account.title
        user.other_name = account.other_name
        user.surname = account.surname
        user.gender = account.gender
        user.academic_rank = account.academic_rank
        user.phone_number = f"+233 20 555 {index + 101:04d}"
        user.college_id = college.id
        user.school_id = school.id
        user.department_id = department.id
        users_by_email[account.email] = user

    await db.flush()
    demo_user_ids = [user.id for user in users_by_email.values()]
    existing_role_rows = (
        await db.execute(
            select(UserRole, Role)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id.in_(demo_user_ids))
        )
    ).all()
    role_rows_by_user: dict[UUID, dict[str, UserRole]] = {user_id: {} for user_id in demo_user_ids}
    for user_role, role in existing_role_rows:
        role_rows_by_user[user_role.user_id][role.key] = user_role

    demo_admin = users_by_email["demo.administrator@utag.com"]
    assigned_at = datetime.now(UTC)
    for account in DEMO_ACCOUNTS:
        user = users_by_email[account.email]
        expected_roles = set(account.roles)
        current_roles = role_rows_by_user[user.id]
        for role_key, user_role in current_roles.items():
            if role_key not in expected_roles:
                await db.delete(user_role)
        for role_key in expected_roles - current_roles.keys():
            role = roles.get(role_key)
            if role is None:
                raise RuntimeError(f"Required demo role is missing: {role_key}")
            db.add(
                UserRole(
                    id=new_id(),
                    user_id=user.id,
                    role_id=role.id,
                    assigned_by_id=demo_admin.id,
                    assigned_at=assigned_at,
                )
            )

    executive_accounts = [row for row in DEMO_ACCOUNTS if row.executive_position]
    executive_user_ids = [users_by_email[row.email].id for row in executive_accounts]
    existing_appointments = {
        (row.user_id, row.position): row
        for row in (
            await db.scalars(
                select(ExecutiveAppointment).where(
                    ExecutiveAppointment.user_id.in_(executive_user_ids)
                )
            )
        ).all()
    }
    for account in executive_accounts:
        user = users_by_email[account.email]
        position = account.executive_position
        if position is None:
            continue
        appointment = existing_appointments.get((user.id, position))
        if appointment is None:
            appointment = ExecutiveAppointment(
                id=new_id(),
                user_id=user.id,
                position=position,
            )
            db.add(appointment)
        appointment.portfolio = account.portfolio
        appointment.summary = (
            f"{user.full_name} is the demo {position} profile for dashboard "
            "and public-site testing."
        )
        appointment.biography_html = (
            f"<p>{user.full_name} is a fictional UG UTAG test profile. "
            "This record contains no real personal information.</p>"
        )
        appointment.social_links = {
            "linkedin": f"https://www.linkedin.com/in/utag-demo-{account.staff_id.lower()}"
        }
        appointment.appointed_on = date(2025, 8, 1)
        appointment.ended_on = None
        appointment.term_number = 1
        appointment.is_acting = False
        appointment.is_active = True
        appointment.is_public = True
        # Demo identities are fictional and intentionally exercise both public
        # contact fields; real appointments default to private contact details.
        appointment.show_email = True
        appointment.show_phone = True

    await db.commit()
    return DemoSeedResult(
        accounts=len(DEMO_ACCOUNTS),
        executive_appointments=len(executive_accounts),
    )
