from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.database import new_id
from utag_api.models import AdSlot, FeatureFlag, OrganizationUnit, SiteSetting
from utag_api.services.query import slugify

# University reference data is deliberately kept in one version-controlled location.
# The structure follows the University's collegiate model: college -> school -> department.
ORGANIZATION_STRUCTURE: Mapping[str, Mapping[str, Sequence[str]]] = {
    "College of Basic and Applied Sciences": {
        "School of Agriculture": (
            "Department of Agricultural Economics and Agribusiness",
            "Department of Agricultural Extension",
            "Department of Animal Science",
            "Department of Crop Science",
            "Department of Family and Consumer Sciences",
            "Department of Soil Science",
        ),
        "School of Biological Sciences": (
            "Department of Animal Biology and Conservation Science",
            "Department of Biochemistry, Cell and Molecular Biology",
            "Department of Botany",
            "Department of Marine and Fisheries Sciences",
            "Department of Microbiology",
            "Department of Nutrition and Food Science",
        ),
        "School of Engineering Sciences": (
            "Department of Agricultural Engineering",
            "Department of Biomedical Engineering",
            "Department of Computer Engineering",
            "Department of Food Process Engineering",
            "Department of Materials Science and Engineering",
        ),
        "School of Physical and Mathematical Sciences": (
            "Department of Chemistry",
            "Department of Computer Science",
            "Department of Earth Science",
            "Department of Mathematics",
            "Department of Physics",
            "Department of Statistics and Actuarial Science",
        ),
        "School of Veterinary Medicine": (
            "Department of Veterinary Anatomy and Physiology",
            "Department of Veterinary Clinical Studies",
            "Department of Veterinary Pathology",
            "Department of Veterinary Public Health and Food Safety",
        ),
    },
    "College of Education": {
        "School of Continuing and Distance Education": (
            "Department of Adult Education and Human Resource Studies",
            "Department of Distance Education",
        ),
        "School of Education and Leadership": (
            "Department of Educational Studies and Leadership",
            "Department of Physical Education and Sport Studies",
            "Department of Teacher Education",
        ),
        "School of Information and Communication Studies": (
            "Department of Communication Studies",
            "Department of Information Studies",
        ),
    },
    "College of Health Sciences": {
        "School of Biomedical and Allied Health Sciences": (
            "Department of Audiology, Speech and Language Therapy",
            "Department of Dietetics",
            "Department of Medical Laboratory Sciences",
            "Department of Occupational Therapy",
            "Department of Physiotherapy",
            "Department of Radiography",
        ),
        "School of Nursing and Midwifery": (
            "Department of Adult Health",
            "Department of Community Health Nursing",
            "Department of Maternal and Child Health Nursing",
            "Department of Mental Health Nursing",
            "Department of Nursing Administration and Education",
        ),
        "School of Pharmacy": (
            "Department of Pharmaceutical Chemistry",
            "Department of Pharmaceutics and Microbiology",
            "Department of Pharmacognosy and Herbal Medicine",
            "Department of Pharmacology and Toxicology",
        ),
        "School of Public Health": (
            "Department of Biostatistics",
            "Department of Epidemiology and Disease Control",
            "Department of Health Policy, Planning and Management",
            "Department of Population, Family and Reproductive Health",
            "Department of Social and Behavioural Sciences",
        ),
        "University of Ghana Dental School": (
            "Department of Adult Oral Health",
            "Department of Biomaterials Science",
            "Department of Child Oral Health and Orthodontics",
        ),
        "University of Ghana Medical School": (
            "Department of Anaesthesia",
            "Department of Anatomy",
            "Department of Chemical Pathology",
            "Department of Child Health",
            "Department of Community Health",
            "Department of Haematology",
            "Department of Medical Biochemistry",
            "Department of Medical Microbiology",
            "Department of Medicine",
            "Department of Obstetrics and Gynaecology",
            "Department of Pathology",
            "Department of Pharmacology",
            "Department of Physiology",
            "Department of Psychiatry",
            "Department of Radiology",
            "Department of Surgery",
        ),
    },
    "College of Humanities": {
        "School of Arts": (
            "Department of History",
            "Department of Philosophy and Classics",
            "Department for the Study of Religions",
        ),
        "School of Languages": (
            "Department of English",
            "Department of French",
            "Department of Linguistics",
            "Department of Modern Languages",
        ),
        "School of Law": (),
        "School of Performing Arts": (
            "Department of Dance Studies",
            "Department of Music",
            "Department of Theatre Arts",
        ),
        "School of Social Sciences": (
            "Department of Economics",
            "Department of Geography and Resource Development",
            "Department of Political Science",
            "Department of Psychology",
            "Department of Social Work",
            "Department of Sociology",
        ),
        "University of Ghana Business School": (
            "Department of Accounting",
            "Department of Finance",
            "Department of Health Services Management",
            "Department of Marketing and Entrepreneurship",
            "Department of Operations and Management Information Systems",
            "Department of Organisation and Human Resource Management",
            "Department of Public Administration",
        ),
    },
}

SITE_SETTINGS: Mapping[str, dict[str, object]] = {
    "site.identity": {
        "name": "University of Ghana UTAG",
        "short_name": "UG UTAG",
        "tagline": "Scholarship, solidarity and service",
    },
    "site.contact": {
        "email": "",
        "phone": "",
        "address": "University of Ghana, Legon, Accra",
        "office_hours": "",
    },
    "site.social": {},
    "site.home": {
        "eyebrow": "University of Ghana Branch",
        "headline": "The academic voice of the University of Ghana",
        "introduction": "A trusted home for members, knowledge and collective action.",
    },
    "site.about": {
        "heading": "A united voice for University of Ghana academics",
        "introduction": (
            "UG UTAG represents teaching and research staff and advances their "
            "academic, professional and economic welfare."
        ),
    },
    "site.resources": {
        "heading": "Public documents and association resources",
        "introduction": (
            "Constitutional, policy and public-interest material approved for public access."
        ),
    },
    "site.footer": {
        "copyright_name": "University of Ghana Branch of UTAG",
        "membership_note": "Internal resources are available through the secure member portal.",
    },
    "site.carousel": {"slides": []},
}

FEATURE_FLAGS = {
    "association-pulse": "Live association activity visualization",
    "public-resources": "Approved external documents on the public Resources page",
    "content-moderation": "Editorial review and publication queue",
    "public-gallery": "Approved galleries and public media",
}

AD_SLOTS = (
    ("top", "Top banner", 1200, 600),
    ("hero", "Hero placement", 1200, 600),
    ("sidebar", "Sidebar placement", 600, 450),
    ("bottom", "Bottom banner", 900, 300),
    ("footer", "Footer banner", 1200, 200),
    ("home-hero", "Home hero sponsor", 1200, 320),
    ("news-sidebar", "News sidebar", 360, 300),
    ("dashboard-partner", "Dashboard partner", 760, 160),
)


async def _upsert_unit(
    db: AsyncSession,
    *,
    unit_type: str,
    name: str,
    parent_id: UUID | None,
) -> OrganizationUnit:
    slug = slugify(f"{unit_type}-{name}")
    unit = await db.scalar(select(OrganizationUnit).where(OrganizationUnit.slug == slug))
    if unit is None:
        unit = OrganizationUnit(
            id=new_id(),
            unit_type=unit_type,
            name=name,
            slug=slug,
            parent_id=parent_id,
            is_active=True,
        )
        db.add(unit)
        await db.flush()
    else:
        unit.name = name
        unit.parent_id = parent_id
        unit.is_active = True
    return unit


async def seed_organization(db: AsyncSession) -> None:
    for college_name, schools in ORGANIZATION_STRUCTURE.items():
        college = await _upsert_unit(
            db,
            unit_type="college",
            name=college_name,
            parent_id=None,
        )
        for school_name, departments in schools.items():
            school = await _upsert_unit(
                db,
                unit_type="school",
                name=school_name,
                parent_id=college.id,
            )
            for department_name in departments:
                await _upsert_unit(
                    db,
                    unit_type="department",
                    name=department_name,
                    parent_id=school.id,
                )


async def seed_portal_defaults(db: AsyncSession) -> None:
    settings = {row.key: row for row in (await db.scalars(select(SiteSetting))).all()}
    for key, value in SITE_SETTINGS.items():
        if key not in settings:
            db.add(SiteSetting(id=new_id(), key=key, value=value, is_public=True))

    flags = {row.key: row for row in (await db.scalars(select(FeatureFlag))).all()}
    for key, description in FEATURE_FLAGS.items():
        if key not in flags:
            db.add(
                FeatureFlag(
                    id=new_id(),
                    key=key,
                    description=description,
                    enabled=True,
                )
            )

    slots = {row.key: row for row in (await db.scalars(select(AdSlot))).all()}
    for key, name, width, height in AD_SLOTS:
        slot = slots.get(key)
        if slot is None:
            db.add(
                AdSlot(
                    id=new_id(),
                    key=key,
                    name=name,
                    width=width,
                    height=height,
                    is_active=True,
                )
            )
        else:
            slot.name = name
            slot.width = width
            slot.height = height

    await seed_organization(db)
    await db.commit()
