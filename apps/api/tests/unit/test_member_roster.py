import io

from openpyxl import Workbook
from sqlalchemy import func, select

from utag_api.database import new_id
from utag_api.models import (
    Conversation,
    ConversationMember,
    OrganizationUnit,
    Role,
    User,
    UserRole,
)
from utag_api.security import hash_password, verify_password
from utag_api.seed_data import seed_organization
from utag_api.services.member_roster import (
    canonical_unit_name,
    canonicalize_rank,
    canonicalize_title,
    normalize_affiliation,
    organization_structure_from_rows,
    parse_member_roster_bytes,
    render_organization_structure,
    split_person_name,
    sync_member_roster,
)

ROSTER_HEADERS = [
    "email",
    "staff_id",
    "other_name",
    "surname",
    "title",
    "rank",
    "college",
    "school",
    "department",
]
CORE_HEADERS = [
    "email",
    "staff_id",
    "other_name",
    "surname",
    "college",
    "school",
    "department",
]


def _workbook_bytes(headers: list[str], rows: list[list[object]], *, title_rows: int = 0) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for index in range(title_rows):
        sheet.append([f"Title row {index + 1}"])
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_parses_offset_headers_and_common_aliases() -> None:
    data = _workbook_bytes(
        [
            "Staff No",
            "Email Address",
            "Name",
            "Rank",
            "College",
            "Faculty",
            "Dept",
            "Title",
        ],
        [
            [
                "1001",
                "ama@example.edu.gh",
                "Dr. Ama Mensah",
                "Snr Lecturer",
                "COLLEGE OF HUMANITIES",
                "Languages",
                "English",
                "Prof",
            ]
        ],
        title_rows=2,
    )
    rows = parse_member_roster_bytes("members.xlsx", data)
    assert len(rows) == 1
    row = rows[0]
    assert row.row_number == 4
    assert row.staff_id == "1001"
    assert row.email == "ama@example.edu.gh"
    assert row.other_name == "Ama"
    assert row.surname == "Mensah"
    assert row.title == "Prof."
    assert row.academic_rank == "Senior Lecturer"
    assert row.college == "College of Humanities"
    assert row.school == "School of Languages"
    assert row.department == "Department of English"


def test_canonical_names_and_person_split() -> None:
    assert canonical_unit_name("HUMANITIES", "college") == "College of Humanities"
    assert canonicalize_title("Dr (Mrs)") == "Dr. (Mrs.)"
    assert canonicalize_rank("Associate Prof") == "Associate Professor"
    assert canonicalize_rank("SENIOR LCTURER") == "Senior Lecturer"
    assert split_person_name(
        full_name="Kwame Asante Boateng",
        other_name="",
        surname="",
    ) == ("Kwame Asante", "Boateng")
    assert (
        canonical_unit_name("COLLEGE OF BASIC & APPLIED SC.", "college")
        == "College of Basic and Applied Sciences"
    )
    assert (
        canonical_unit_name("SCH. OF PHYSICAL & MATH. SC.", "school")
        == "School of Physical and Mathematical Sciences"
    )
    assert canonical_unit_name("CENTRAL ADMINISTRATION", "college") == "Central Administration"


def test_parses_hr_staff_email_and_job_title_headers() -> None:
    data = _workbook_bytes(
        [
            "STAFF_ID",
            "TITLE",
            "FIRST_NAMES",
            "SURNAME",
            "JOB_TITLE",
            "DEPARTMENT",
            "SCHOOL",
            "COLLEGE",
            "STAFF_EMAIL",
        ],
        [
            [
                27867,
                "DR.",
                "BENJAMIN",
                "ADJEI-MENSAH",
                "LECTURER",
                "DEPARTMENT OF ANIMAL SCIENCE",
                "SCHOOL OF AGRICULTURE",
                "COLLEGE OF BASIC & APPLIED SC.",
                "badjei-mensah@ug.edu.gh",
            ]
        ],
    )
    rows = parse_member_roster_bytes("members.xlsx", data)
    assert len(rows) == 1
    row = rows[0]
    assert row.staff_id == "27867"
    assert row.email == "badjei-mensah@ug.edu.gh"
    assert row.other_name == "BENJAMIN"
    assert row.surname == "ADJEI-MENSAH"
    assert row.title == "Dr."
    assert row.academic_rank == "Lecturer"
    assert row.college == "College of Basic and Applied Sciences"
    assert row.school == "School of Agriculture"
    assert row.department == "Department of Animal Science"


def test_lifts_college_repeated_as_school_and_collapses_matching_secretariat() -> None:
    college, school, department = normalize_affiliation(
        "COLLEGE OF BASIC & APPLIED SC.",
        "COLLEGE OF BASIC & APPLIED SC.",
        "FOREST AND HORTICULTURAL CROP RESEARCH CENTRE",
    )
    assert college == "College of Basic and Applied Sciences"
    assert school == "Forest and Horticultural Crop Research Centre"
    assert department == ""

    college, school, department = normalize_affiliation(
        "COLLEGE OF HUMANITIES",
        "SCHOOL OF LAW",
        "SCHOOL OF LAW SECRETARIAT",
    )
    assert college == "College of Humanities"
    assert school == "School of Law"
    assert department == ""

    college, school, department = normalize_affiliation(
        "CENTRAL ADMINISTRATION",
        "CENTRAL ADMINISTRATION",
        "THE VICE-CHANCELLOR SECRETARIAT",
    )
    assert college == "Central Administration"
    assert school == "The Vice-Chancellor"
    assert department == ""
    assert (
        canonical_unit_name("UNIV. OF GHANA MEDICAL SCHOOL", "school")
        == "University of Ghana Medical School"
    )
    assert canonical_unit_name("SCHOOL OF NURSING & MIDWIFERY", "school") == (
        "School of Nursing and Midwifery"
    )
    assert canonical_unit_name("GEMP OFFICE", "department") == "GEMP Office"


def test_organization_structure_keeps_blank_department_schools() -> None:
    data = _workbook_bytes(
        CORE_HEADERS,
        [
            [
                "law@example.edu.gh",
                "1",
                "Ama",
                "Law",
                "College of Humanities",
                "School of Law",
                "",
            ],
            [
                "eng@example.edu.gh",
                "2",
                "Kofi",
                "English",
                "College of Humanities",
                "School of Languages",
                "Department of English",
            ],
        ],
    )
    rows = parse_member_roster_bytes("members.xlsx", data)
    structure = organization_structure_from_rows(rows)
    assert structure["College of Humanities"]["School of Law"] == ()
    assert structure["College of Humanities"]["School of Languages"] == ("Department of English",)
    rendered = render_organization_structure(structure)
    assert '"School of Law": ()' in rendered
    assert '"Department of English",' in rendered


async def test_keeps_same_named_departments_under_different_schools(
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    data = _workbook_bytes(
        CORE_HEADERS,
        [
            [
                "anatomy.ba@example.edu.gh",
                "1",
                "Ama",
                "Allied",
                "College of Health Sciences",
                "School of Biomedical and Allied Health Sciences",
                "Department of Anatomy",
            ],
            [
                "anatomy.med@example.edu.gh",
                "2",
                "Kofi",
                "Medical",
                "College of Health Sciences",
                "University of Ghana Medical School",
                "Department of Anatomy",
            ],
        ],
    )
    async with session_factory() as session:
        await sync_member_roster(session, parse_member_roster_bytes("members.xlsx", data))
        await session.commit()
        anatomies = list(
            (
                await session.scalars(
                    select(OrganizationUnit).where(
                        OrganizationUnit.unit_type == "department",
                        OrganizationUnit.name == "Department of Anatomy",
                    )
                )
            ).all()
        )
        ama = await session.scalar(select(User).where(User.email == "anatomy.ba@example.edu.gh"))
        kofi = await session.scalar(select(User).where(User.email == "anatomy.med@example.edu.gh"))
        assert len(anatomies) == 2
        assert anatomies[0].parent_id != anatomies[1].parent_id
        assert ama is not None
        assert kofi is not None
        assert ama.department_id != kofi.department_id
        assert ama.school_id != kofi.school_id


async def test_relinks_org_without_touching_password(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        await seed_organization(session)
        english = await session.scalar(
            select(OrganizationUnit).where(
                OrganizationUnit.unit_type == "department",
                OrganizationUnit.name == "Department of English",
            )
        )
        assert english is not None
        school = await session.get(OrganizationUnit, english.parent_id)
        assert school is not None
        college = await session.get(OrganizationUnit, school.parent_id)
        assert college is not None
        user = User(
            id=new_id(),
            email="kwame@example.edu.gh",
            staff_id="UG100",
            password_hash=hash_password("KeepThisPassword1"),
            must_change_password=False,
            status="active",
            title="",
            other_name="Kwame",
            surname="Asante",
            academic_rank=None,
            college_id=college.id,
            school_id=school.id,
            department_id=english.id,
        )
        session.add(user)
        await session.commit()
        password_hash = user.password_hash

    data = _workbook_bytes(
        ROSTER_HEADERS,
        [
            [
                "kwame@example.edu.gh",
                "UG100",
                "Kwame",
                "Asante",
                "Dr.",
                "Lecturer",
                "College of Humanities",
                "School of Arts",
                "Department of History",
            ]
        ],
    )
    rows = parse_member_roster_bytes("members.xlsx", data)
    async with session_factory() as session:
        result = await sync_member_roster(session, rows)
        await session.commit()
        updated = await session.scalar(select(User).where(User.email == "kwame@example.edu.gh"))
        history = await session.scalar(
            select(OrganizationUnit).where(OrganizationUnit.name == "Department of History")
        )
        assert updated is not None
        assert history is not None
        assert result.members_relinked == 1
        assert result.titles_filled == 1
        assert result.ranks_filled == 1
        assert updated.department_id == history.id
        assert updated.title == "Dr."
        assert updated.academic_rank == "Lecturer"
        assert updated.password_hash == password_hash
        assert updated.must_change_password is False
        assert verify_password(updated.password_hash, "KeepThisPassword1")[0] is True


async def test_does_not_overwrite_existing_title_or_rank(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        user = User(
            id=new_id(),
            email="efua@example.edu.gh",
            staff_id="UG200",
            password_hash=hash_password("KeepThisPassword1"),
            status="active",
            title="Prof.",
            other_name="Efua",
            surname="Owusu",
            academic_rank="Professor",
        )
        session.add(user)
        await session.commit()

    data = _workbook_bytes(
        ROSTER_HEADERS,
        [
            [
                "efua@example.edu.gh",
                "UG200",
                "Efua",
                "Owusu",
                "Dr.",
                "Lecturer",
                "College of Humanities",
                "School of Law",
                "",
            ]
        ],
    )
    async with session_factory() as session:
        result = await sync_member_roster(session, parse_member_roster_bytes("members.xlsx", data))
        await session.commit()
        updated = await session.scalar(select(User).where(User.email == "efua@example.edu.gh"))
        law = await session.scalar(
            select(OrganizationUnit).where(
                OrganizationUnit.unit_type == "school",
                OrganizationUnit.name == "School of Law",
            )
        )
        assert updated is not None
        assert law is not None
        assert result.titles_filled == 0
        assert result.ranks_filled == 0
        assert updated.title == "Prof."
        assert updated.academic_rank == "Professor"
        assert updated.school_id == law.id
        assert updated.department_id is None


async def test_creates_missing_member_with_staff_password(session_factory) -> None:  # type: ignore[no-untyped-def]
    data = _workbook_bytes(
        CORE_HEADERS,
        [
            [
                "new.member@example.edu.gh",
                "UG300",
                "Akosua",
                "Boateng",
                "College of Humanities",
                "School of Law",
                "",
            ]
        ],
    )
    async with session_factory() as session:
        result = await sync_member_roster(session, parse_member_roster_bytes("members.xlsx", data))
        await session.commit()
        created = await session.scalar(
            select(User).where(User.email == "new.member@example.edu.gh")
        )
        member_role = await session.scalar(select(Role).where(Role.key == "member"))
        assert created is not None
        assert member_role is not None
        assert result.members_created == 1
        assert created.must_change_password is True
        assert created.status == "active"
        assert verify_password(created.password_hash, "UG300")[0] is True
        role = await session.scalar(
            select(UserRole.id).where(
                UserRole.user_id == created.id, UserRole.role_id == member_role.id
            )
        )
        assert role is not None
        groups = list(
            (
                await session.scalars(
                    select(Conversation.title)
                    .join(ConversationMember, ConversationMember.conversation_id == Conversation.id)
                    .where(ConversationMember.user_id == created.id)
                )
            ).all()
        )
        assert "UTAG UG" in groups
        assert "School: School of Law" in groups


async def test_staff_id_email_clash_is_skipped(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        session.add_all(
            [
                User(
                    id=new_id(),
                    email="one@example.edu.gh",
                    staff_id="UG400",
                    password_hash=hash_password("KeepThisPassword1"),
                    status="active",
                    title="Dr.",
                    other_name="One",
                    surname="Person",
                ),
                User(
                    id=new_id(),
                    email="two@example.edu.gh",
                    staff_id="UG401",
                    password_hash=hash_password("KeepThisPassword1"),
                    status="active",
                    title="Dr.",
                    other_name="Two",
                    surname="Person",
                ),
            ]
        )
        await session.commit()
    data = _workbook_bytes(
        CORE_HEADERS,
        [
            [
                "one@example.edu.gh",
                "UG401",
                "One",
                "Person",
                "College of Humanities",
                "School of Law",
                "",
            ]
        ],
    )
    async with session_factory() as session:
        result = await sync_member_roster(session, parse_member_roster_bytes("members.xlsx", data))
        one = await session.scalar(select(User).where(User.email == "one@example.edu.gh"))
        two = await session.scalar(select(User).where(User.email == "two@example.edu.gh"))
        assert one is not None
        assert two is not None
        assert result.members_relinked == 0
        assert result.conflicts
        assert one.staff_id == "UG400"
        assert one.college_id is None
        assert two.staff_id == "UG401"


async def test_prunes_unreferenced_leftover_and_retains_linked_and_committees(
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        await seed_organization(session)
        leftover = OrganizationUnit(
            id=new_id(),
            unit_type="department",
            name="Obsolete Seeded Department",
            slug="obsolete-seeded-department",
            is_active=True,
        )
        linked_leftover = OrganizationUnit(
            id=new_id(),
            unit_type="department",
            name="Still Linked Seeded Department",
            slug="still-linked-seeded-department",
            is_active=True,
        )
        committee = OrganizationUnit(
            id=new_id(),
            unit_type="committee",
            name="Welfare Committee",
            slug="welfare-committee",
            is_active=True,
        )
        session.add_all([leftover, linked_leftover, committee])
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert administrator is not None
        administrator.department_id = linked_leftover.id
        await session.commit()
        leftover_id = leftover.id
        linked_id = linked_leftover.id
        committee_id = committee.id

    data = _workbook_bytes(
        CORE_HEADERS,
        [
            [
                "fresh@example.edu.gh",
                "UG500",
                "Fresh",
                "Member",
                "College of Humanities",
                "School of Law",
                "",
            ]
        ],
    )
    async with session_factory() as session:
        result = await sync_member_roster(session, parse_member_roster_bytes("members.xlsx", data))
        await session.commit()
        assert await session.get(OrganizationUnit, leftover_id) is None
        assert await session.get(OrganizationUnit, linked_id) is not None
        assert await session.get(OrganizationUnit, committee_id) is not None
        assert result.units_pruned >= 1
        assert any("Still Linked Seeded Department" in item for item in result.retained_units)


async def test_dry_run_session_rollback_leaves_database_unchanged(
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    data = _workbook_bytes(
        CORE_HEADERS,
        [
            [
                "dry.run@example.edu.gh",
                "UG600",
                "Dry",
                "Run",
                "College of Humanities",
                "School of Law",
                "",
            ]
        ],
    )
    async with session_factory() as session:
        before = await session.scalar(select(func.count()).select_from(User))
        await sync_member_roster(session, parse_member_roster_bytes("members.xlsx", data))
        await session.rollback()

    async with session_factory() as session:
        after = await session.scalar(select(func.count()).select_from(User))
        created = await session.scalar(select(User).where(User.email == "dry.run@example.edu.gh"))
        assert after == before
        assert created is None


async def test_fills_blank_staff_id_when_email_matches(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        session.add(
            User(
                id=new_id(),
                email="blank.staff@example.edu.gh",
                staff_id=None,
                password_hash=hash_password("KeepThisPassword1"),
                status="active",
                title="Dr.",
                other_name="Blank",
                surname="Staff",
            )
        )
        await session.commit()
    data = _workbook_bytes(
        CORE_HEADERS,
        [
            [
                "blank.staff@example.edu.gh",
                "UG700",
                "Blank",
                "Staff",
                "College of Humanities",
                "School of Law",
                "",
            ]
        ],
    )
    async with session_factory() as session:
        result = await sync_member_roster(session, parse_member_roster_bytes("members.xlsx", data))
        await session.commit()
        updated = await session.scalar(
            select(User).where(User.email == "blank.staff@example.edu.gh")
        )
        assert updated is not None
        assert result.staff_ids_filled == 1
        assert updated.staff_id == "UG700"
