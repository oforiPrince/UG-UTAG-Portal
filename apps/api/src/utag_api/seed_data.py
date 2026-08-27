import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.database import new_id
from utag_api.models import (
    AdPlan,
    AdSlot,
    Announcement,
    Conversation,
    ConversationInvite,
    ConversationMember,
    Document,
    FeatureFlag,
    Message,
    OrganizationUnit,
    SiteSetting,
    User,
)
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
            "Department of Restorative Dentistry",
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

# Canonical office hours for public contact surfaces.
CANONICAL_OFFICE_HOURS = "Monday-Friday, 9:00 AM-5:00 PM"

# Known stale values previously seeded or hard-coded; reconciled on each seed run.
STALE_OFFICE_HOURS = frozenset(
    {
        "Monday-Friday, 9:00 AM-6:00 PM",
        "Monday–Friday, 9:00 AM–6:00 PM",  # noqa: RUF001 - exact legacy value
        "Monday to Friday: 9:00 AM - 6:00 PM",
        "Mon – Fri : 9:00 – 18:00",  # noqa: RUF001 - exact legacy value
        "Mon - Fri : 9:00 - 18:00",
    }
)

SITE_SETTINGS: Mapping[str, dict[str, object]] = {
    "site.identity": {
        "name": "University of Ghana UTAG",
        "short_name": "UG UTAG",
        "tagline": "Scholarship, solidarity, and service",
    },
    "site.contact": {
        "email": "utagoffice@ug.edu.gh",
        "phone": "+233 (0) 24 427 7275",
        "address": "University of Ghana, Legon, Accra",
        "office_hours": CANONICAL_OFFICE_HOURS,
    },
    "site.social": {},
    "site.home": {
        "eyebrow": "University of Ghana Branch",
        "headline": "The academic voice of the University of Ghana",
        "introduction": "A trusted home for members, knowledge, and collective action.",
    },
    "site.about": {
        "heading": "A united voice for University of Ghana academics",
        "introduction": (
            "UG UTAG represents teaching and research staff and advances their "
            "academic, professional, and economic welfare."
        ),
    },
    "site.resources": {
        "heading": "Public documents and association resources",
        "introduction": (
            "Constitutional, policy, and public-interest material approved for public access."
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
    # key, name, width, height, location, is_active
    ("home-after-hero", "Home after hero", 970, 250, "Home · after hero", True),
    ("news-sidebar", "News listing rail", 300, 250, "News listing · sidebar", True),
    ("events-sidebar", "Events listing rail", 300, 250, "Events listing · sidebar", True),
    (
        "content-inline",
        "Article / detail strip",
        728,
        90,
        "News, events, gallery detail · after hero",
        True,
    ),
    ("footer", "Site footer strip", 970, 90, "All public pages · above footer", True),
)

# name, slot_key, price, duration_days, description
AD_PLANS = (
    (
        "Home after-hero · 30 days",
        "home-after-hero",
        "1500.00",
        30,
        "970x250 placement on the home page after the hero.",
    ),
    (
        "News sidebar · 30 days",
        "news-sidebar",
        "900.00",
        30,
        "300x250 medium rectangle on the news listing page.",
    ),
    (
        "Events sidebar · 30 days",
        "events-sidebar",
        "900.00",
        30,
        "300x250 medium rectangle on the events listing page.",
    ),
    (
        "Content inline · 30 days",
        "content-inline",
        "750.00",
        30,
        "728x90 leaderboard on news, events, and gallery detail pages.",
    ),
    (
        "Site footer · 30 days",
        "footer",
        "1200.00",
        30,
        "970x90 strip above the site footer on all public pages.",
    ),
)


@dataclass(frozen=True, slots=True)
class OrganizationSeedResult:
    canonical_ids: frozenset[UUID]
    created: int
    updated: int


@dataclass(frozen=True, slots=True)
class OrganizationReconcileResult:
    canonical_created: int
    canonical_updated: int
    users_relinked: int
    announcement_audiences_relinked: int
    document_audiences_relinked: int
    unresolved_users: int
    legacy_units_prunable: int
    legacy_units_pruned: int
    legacy_units_retained: int
    unresolved_user_ids: tuple[UUID, ...]


def organization_name_key(value: str) -> str:
    """Normalize harmless legacy spelling differences without fuzzy matching."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    words = re.findall(r"[a-z0-9]+", normalized)
    aliases = {"dept": "department", "univ": "university"}
    return " ".join(aliases.get(word, word) for word in words if word != "of")


async def _available_organization_slug(
    db: AsyncSession,
    *,
    unit_type: str,
    name: str,
) -> str:
    base = slugify(f"{unit_type}-{name}")
    slug = base
    suffix = 2
    while await db.scalar(select(OrganizationUnit.id).where(OrganizationUnit.slug == slug)):
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


async def _upsert_unit(
    db: AsyncSession,
    *,
    unit_type: str,
    name: str,
    parent_id: UUID | None,
) -> tuple[OrganizationUnit, bool, bool]:
    candidates = list(
        (
            await db.scalars(
                select(OrganizationUnit).where(OrganizationUnit.unit_type == unit_type)
            )
        ).all()
    )
    name_key = organization_name_key(name)
    matching = [item for item in candidates if organization_name_key(item.name) == name_key]
    unit = next((item for item in matching if item.parent_id == parent_id), None)
    if unit is None and len(matching) == 1:
        # Reuse an unambiguous earlier seed/migration row so member references
        # keep their stable UUID while its parent is corrected.
        unit = matching[0]
    created = unit is None
    updated = False
    if unit is None:
        unit = OrganizationUnit(
            id=new_id(),
            unit_type=unit_type,
            name=name,
            slug=await _available_organization_slug(
                db,
                unit_type=unit_type,
                name=name,
            ),
            parent_id=parent_id,
            is_active=True,
        )
        db.add(unit)
        await db.flush()
    else:
        updated = unit.name != name or unit.parent_id != parent_id or not unit.is_active
        unit.name = name
        unit.parent_id = parent_id
        unit.is_active = True
    return unit, created, updated


async def seed_organization(db: AsyncSession) -> OrganizationSeedResult:
    canonical_ids: set[UUID] = set()
    created = 0
    updated = 0
    for college_name, schools in ORGANIZATION_STRUCTURE.items():
        college, was_created, was_updated = await _upsert_unit(
            db,
            unit_type="college",
            name=college_name,
            parent_id=None,
        )
        canonical_ids.add(college.id)
        created += int(was_created)
        updated += int(was_updated)
        for school_name, departments in schools.items():
            school, was_created, was_updated = await _upsert_unit(
                db,
                unit_type="school",
                name=school_name,
                parent_id=college.id,
            )
            canonical_ids.add(school.id)
            created += int(was_created)
            updated += int(was_updated)
            for department_name in departments:
                department, was_created, was_updated = await _upsert_unit(
                    db,
                    unit_type="department",
                    name=department_name,
                    parent_id=school.id,
                )
                canonical_ids.add(department.id)
                created += int(was_created)
                updated += int(was_updated)
    await db.flush()
    return OrganizationSeedResult(
        canonical_ids=frozenset(canonical_ids),
        created=created,
        updated=updated,
    )


def _unit_context_names(
    unit: OrganizationUnit,
    units_by_id: dict[UUID, OrganizationUnit],
) -> set[str]:
    names: set[str] = set()
    current: OrganizationUnit | None = unit
    visited: set[UUID] = set()
    while current is not None and current.id not in visited:
        visited.add(current.id)
        names.add(organization_name_key(current.name))
        current = units_by_id.get(current.parent_id) if current.parent_id else None
    return names


def _canonical_chain(
    unit: OrganizationUnit,
    canonical_ids: frozenset[UUID],
    units_by_id: dict[UUID, OrganizationUnit],
) -> dict[str, OrganizationUnit]:
    chain: dict[str, OrganizationUnit] = {}
    current: OrganizationUnit | None = unit
    visited: set[UUID] = set()
    while current is not None and current.id not in visited:
        visited.add(current.id)
        if current.id not in canonical_ids:
            break
        chain[current.unit_type] = current
        current = units_by_id.get(current.parent_id) if current.parent_id else None
    return chain


def _canonical_match(
    source: OrganizationUnit,
    *,
    canonical_by_name: dict[str, list[OrganizationUnit]],
    canonical_ids: frozenset[UUID],
    units_by_id: dict[UUID, OrganizationUnit],
    context_names: set[str] | None = None,
) -> OrganizationUnit | None:
    if source.id in canonical_ids:
        return source
    if source.legacy_id is None:
        return None
    candidates = canonical_by_name.get(organization_name_key(source.name), [])
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        return None
    context = context_names or _unit_context_names(source, units_by_id)
    scored = [
        (
            sum(
                organization_name_key(item.name) in context
                for item in _canonical_chain(candidate, canonical_ids, units_by_id).values()
                if item.id != candidate.id
            ),
            candidate,
        )
        for candidate in candidates
    ]
    highest = max(score for score, _ in scored)
    winners = [candidate for score, candidate in scored if score == highest]
    return winners[0] if highest > 0 and len(winners) == 1 else None


def _unit_depth(unit: OrganizationUnit, units_by_id: dict[UUID, OrganizationUnit]) -> int:
    depth = 0
    current = unit
    visited: set[UUID] = set()
    while current.parent_id is not None and current.id not in visited:
        visited.add(current.id)
        parent = units_by_id.get(current.parent_id)
        if parent is None:
            break
        depth += 1
        current = parent
    return depth


def _relink_unit_audiences(
    records: Sequence[Announcement | Document],
    replacements: Mapping[UUID, UUID],
) -> int:
    records_relinked = 0
    for record in records:
        changed = False
        audiences: list[dict[str, str]] = []
        for audience in record.audiences:
            updated = dict(audience)
            if updated.get("type") == "unit":
                try:
                    source_id = UUID(str(updated.get("value")))
                except ValueError:
                    source_id = None
                replacement_id = replacements.get(source_id) if source_id else None
                if replacement_id is not None:
                    updated["value"] = str(replacement_id)
                    changed = True
            audiences.append(updated)
        if changed:
            record.audiences = audiences
            records_relinked += 1
    return records_relinked


def _referenced_unit_ids(records: Sequence[Announcement | Document]) -> set[UUID]:
    referenced: set[UUID] = set()
    for record in records:
        for audience in record.audiences:
            if audience.get("type") != "unit":
                continue
            try:
                referenced.add(UUID(str(audience.get("value"))))
            except ValueError:
                continue
    return referenced


async def reconcile_organization(
    db: AsyncSession,
    *,
    prune_unlinked: bool = False,
) -> OrganizationReconcileResult:
    """Reconcile imported legacy affiliations to the canonical UG hierarchy.

    Only deterministic normalized-name matches are applied. Imported rows that
    remain linked or ambiguous are retained, and only imported legacy rows are
    eligible for pruning.
    """
    seed_result = await seed_organization(db)
    units = list((await db.scalars(select(OrganizationUnit).with_for_update())).all())
    units_by_id = {item.id: item for item in units}
    canonical_units = [item for item in units if item.id in seed_result.canonical_ids]
    canonical_by_name: dict[str, list[OrganizationUnit]] = {}
    for item in canonical_units:
        canonical_by_name.setdefault(organization_name_key(item.name), []).append(item)

    replacements: dict[UUID, UUID] = {}
    for item in units:
        match = _canonical_match(
            item,
            canonical_by_name=canonical_by_name,
            canonical_ids=seed_result.canonical_ids,
            units_by_id=units_by_id,
        )
        if match is not None and match.id != item.id:
            replacements[item.id] = match.id

    users = list((await db.scalars(select(User).with_for_update())).all())
    users_relinked = 0
    unresolved_user_ids: list[UUID] = []
    for user in users:
        current_ids = [
            unit_id
            for unit_id in (user.college_id, user.school_id, user.department_id)
            if unit_id is not None
        ]
        if not current_ids:
            continue
        source_units = [units_by_id[unit_id] for unit_id in current_ids if unit_id in units_by_id]
        context_names = {
            name for source in source_units for name in _unit_context_names(source, units_by_id)
        }
        resolved: list[OrganizationUnit] = []
        unresolved = False
        for source in source_units:
            match = _canonical_match(
                source,
                canonical_by_name=canonical_by_name,
                canonical_ids=seed_result.canonical_ids,
                units_by_id=units_by_id,
                context_names=context_names,
            )
            if match is None:
                unresolved = True
                break
            resolved.append(match)
        if unresolved or len(source_units) != len(current_ids):
            unresolved_user_ids.append(user.id)
            continue

        proposed: dict[str, OrganizationUnit] = {}
        conflict = False
        for match in resolved:
            for unit_type, canonical in _canonical_chain(
                match,
                seed_result.canonical_ids,
                units_by_id,
            ).items():
                existing = proposed.get(unit_type)
                if existing is not None and existing.id != canonical.id:
                    conflict = True
                    break
                proposed[unit_type] = canonical
            if conflict:
                break
        if conflict:
            unresolved_user_ids.append(user.id)
            continue

        proposed_college = proposed.get("college")
        proposed_school = proposed.get("school")
        proposed_department = proposed.get("department")
        next_ids = (
            proposed_college.id if proposed_college else None,
            proposed_school.id if proposed_school else None,
            proposed_department.id if proposed_department else None,
        )
        current = (user.college_id, user.school_id, user.department_id)
        if next_ids != current:
            user.college_id, user.school_id, user.department_id = next_ids
            users_relinked += 1

    announcements = list((await db.scalars(select(Announcement).with_for_update())).all())
    documents = list((await db.scalars(select(Document).with_for_update())).all())
    announcement_audiences_relinked = _relink_unit_audiences(announcements, replacements)
    document_audiences_relinked = _relink_unit_audiences(documents, replacements)

    system_groups = list(
        (
            await db.scalars(
                select(Conversation)
                .where(Conversation.direct_key.like("system:%"))
                .with_for_update()
            )
        ).all()
    )
    system_group_by_unit_id: dict[UUID, Conversation] = {}
    for conversation in system_groups:
        direct_key = conversation.direct_key or ""
        prefix, _, raw_unit_id = direct_key.rpartition(":")
        if prefix not in {"system:school", "system:department"}:
            continue
        try:
            system_group_by_unit_id[UUID(raw_unit_id)] = conversation
        except ValueError:
            continue
    system_group_ids = [conversation.id for conversation in system_group_by_unit_id.values()]
    linked_system_group_ids: set[UUID] = set()
    if system_group_ids:
        linked_system_group_ids.update(
            (
                await db.scalars(
                    select(ConversationMember.conversation_id).where(
                        ConversationMember.conversation_id.in_(system_group_ids)
                    )
                )
            ).all()
        )
        linked_system_group_ids.update(
            (
                await db.scalars(
                    select(ConversationInvite.conversation_id).where(
                        ConversationInvite.conversation_id.in_(system_group_ids)
                    )
                )
            ).all()
        )
        linked_system_group_ids.update(
            (
                await db.scalars(
                    select(Message.conversation_id).where(
                        Message.conversation_id.in_(system_group_ids)
                    )
                )
            ).all()
        )

    await db.flush()

    directly_referenced = {
        unit_id
        for user in users
        for unit_id in (user.college_id, user.school_id, user.department_id)
        if unit_id is not None
    }
    directly_referenced.update(_referenced_unit_ids(announcements))
    directly_referenced.update(_referenced_unit_ids(documents))
    directly_referenced.update(
        unit_id
        for unit_id, conversation in system_group_by_unit_id.items()
        if conversation.id in linked_system_group_ids
    )

    legacy_candidates = {
        item.id
        for item in units
        if item.legacy_id is not None and item.id not in seed_result.canonical_ids
    }
    protected = legacy_candidates.intersection(directly_referenced)
    changed = True
    while changed:
        changed = False
        for item in units:
            if item.parent_id not in legacy_candidates:
                continue
            if (
                item.id not in legacy_candidates or item.id in protected
            ) and item.parent_id not in protected:
                protected.add(item.parent_id)
                changed = True

    prunable = legacy_candidates - protected
    pruned = 0
    if prune_unlinked:
        for item in sorted(
            (units_by_id[unit_id] for unit_id in prunable),
            key=lambda value: _unit_depth(value, units_by_id),
            reverse=True,
        ):
            empty_system_group = system_group_by_unit_id.get(item.id)
            if empty_system_group is not None:
                await db.delete(empty_system_group)
            await db.delete(item)
            pruned += 1
        await db.flush()

    return OrganizationReconcileResult(
        canonical_created=seed_result.created,
        canonical_updated=seed_result.updated,
        users_relinked=users_relinked,
        announcement_audiences_relinked=announcement_audiences_relinked,
        document_audiences_relinked=document_audiences_relinked,
        unresolved_users=len(unresolved_user_ids),
        legacy_units_prunable=len(prunable),
        legacy_units_pruned=pruned,
        legacy_units_retained=len(protected),
        unresolved_user_ids=tuple(unresolved_user_ids),
    )


def reconcile_office_hours(value: dict[str, object]) -> dict[str, object]:
    """Rewrite known stale office-hours strings without touching other contact fields."""
    current = value.get("office_hours")
    if not isinstance(current, str):
        return value
    normalized = current.strip()
    if normalized not in STALE_OFFICE_HOURS:
        return value
    return {**value, "office_hours": CANONICAL_OFFICE_HOURS}


async def seed_portal_defaults(db: AsyncSession) -> None:
    settings = {row.key: row for row in (await db.scalars(select(SiteSetting))).all()}
    for key, value in SITE_SETTINGS.items():
        if key not in settings:
            db.add(SiteSetting(id=new_id(), key=key, value=value, is_public=True))

    contact = settings.get("site.contact")
    if contact is not None and isinstance(contact.value, dict):
        updated = reconcile_office_hours(contact.value)
        if updated is not contact.value:
            contact.value = updated

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
    for key, name, width, height, location, is_active in AD_SLOTS:
        slot = slots.get(key)
        if slot is None:
            slot = AdSlot(
                id=new_id(),
                key=key,
                name=name,
                width=width,
                height=height,
                location=location,
                is_active=is_active,
            )
            db.add(slot)
            slots[key] = slot
        else:
            slot.name = name
            slot.width = width
            slot.height = height
            slot.location = location
            slot.is_active = is_active

    await db.flush()
    plans = {row.name: row for row in (await db.scalars(select(AdPlan))).all()}
    for name, slot_key, price, duration_days, description in AD_PLANS:
        slot = slots.get(slot_key)
        if slot is None:
            continue
        plan = plans.get(name)
        if plan is None:
            db.add(
                AdPlan(
                    id=new_id(),
                    slot_id=slot.id,
                    name=name,
                    description=description,
                    price=Decimal(price),
                    duration_days=duration_days,
                    is_active=True,
                )
            )
        else:
            plan.slot_id = slot.id
            plan.description = description
            plan.price = Decimal(price)
            plan.duration_days = duration_days
            plan.is_active = True

    await seed_organization(db)
    await db.commit()
