from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.errors import ApiError
from utag_api.models import OrganizationUnit


def organization_assignment_errors(
    units: dict[UUID, OrganizationUnit],
    *,
    school_id: UUID | None,
    college_id: UUID | None,
    department_id: UUID | None,
) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    expected = (
        ("school_id", school_id, "school"),
        ("college_id", college_id, "college"),
        ("department_id", department_id, "department"),
    )
    for field, unit_id, unit_type in expected:
        if unit_id is None:
            continue
        unit = units.get(unit_id)
        if unit is None or unit.unit_type != unit_type or not unit.is_active:
            errors.append((field, f"Select a valid active {unit_type}"))

    school = units.get(school_id) if school_id else None
    department = units.get(department_id) if department_id else None
    if school and school.unit_type == "school" and school.parent_id != college_id:
        errors.append(("college_id", "The selected school does not belong to this college"))
    if department and department.unit_type == "department" and department.parent_id != school_id:
        errors.append(("school_id", "The selected department does not belong to this school"))
    return errors


async def validate_organization_assignment(
    db: AsyncSession,
    *,
    school_id: UUID | None,
    college_id: UUID | None,
    department_id: UUID | None,
) -> None:
    unit_ids = {
        unit_id for unit_id in (school_id, college_id, department_id) if unit_id is not None
    }
    units = {
        unit.id: unit
        for unit in (
            await db.scalars(select(OrganizationUnit).where(OrganizationUnit.id.in_(unit_ids)))
        ).all()
    }
    errors = organization_assignment_errors(
        units,
        school_id=school_id,
        college_id=college_id,
        department_id=department_id,
    )
    if errors:
        field, message = errors[0]
        raise ApiError(
            422,
            "organization_unit_invalid",
            message,
            details={"field": field},
        )
