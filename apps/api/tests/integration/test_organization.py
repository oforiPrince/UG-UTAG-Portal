from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select

from utag_api.models import User


async def test_organization_hierarchy_requires_valid_parents(client: AsyncClient) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}

    orphan_school = await client.post(
        "/api/v1/organization/units",
        headers=headers,
        json={"unit_type": "school", "name": "Orphan School"},
    )
    assert orphan_school.status_code == 422
    assert orphan_school.json()["error"]["code"] == "parent_unit_invalid"

    college = await client.post(
        "/api/v1/organization/units",
        headers=headers,
        json={"unit_type": "college", "name": "College of Test Studies"},
    )
    assert college.status_code == 201
    school = await client.post(
        "/api/v1/organization/units",
        headers=headers,
        json={
            "unit_type": "school",
            "name": "School of Test Studies",
            "parent_id": college.json()["id"],
        },
    )
    assert school.status_code == 201
    department = await client.post(
        "/api/v1/organization/units",
        headers=headers,
        json={
            "unit_type": "department",
            "name": "Department of Test Studies",
            "parent_id": school.json()["id"],
        },
    )
    assert department.status_code == 201

    wrong_parent = await client.post(
        "/api/v1/organization/units",
        headers=headers,
        json={
            "unit_type": "department",
            "name": "Department with Wrong Parent",
            "parent_id": college.json()["id"],
        },
    )
    assert wrong_parent.status_code == 422

    schools = await client.get(
        "/api/v1/organization/units",
        params={"unit_type": "school"},
    )
    assert schools.status_code == 200
    assert [item["name"] for item in schools.json()] == ["School of Test Studies"]
    assert schools.json()[0]["parent_name"] == "College of Test Studies"


async def test_reparenting_units_keeps_member_affiliations_consistent(
    client: AsyncClient,
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}

    first_college = (
        await client.post(
            "/api/v1/organization/units",
            headers=headers,
            json={"unit_type": "college", "name": "First College"},
        )
    ).json()
    second_college = (
        await client.post(
            "/api/v1/organization/units",
            headers=headers,
            json={"unit_type": "college", "name": "Second College"},
        )
    ).json()
    first_school = (
        await client.post(
            "/api/v1/organization/units",
            headers=headers,
            json={
                "unit_type": "school",
                "name": "First School",
                "parent_id": first_college["id"],
            },
        )
    ).json()
    second_school = (
        await client.post(
            "/api/v1/organization/units",
            headers=headers,
            json={
                "unit_type": "school",
                "name": "Second School",
                "parent_id": second_college["id"],
            },
        )
    ).json()
    department = (
        await client.post(
            "/api/v1/organization/units",
            headers=headers,
            json={
                "unit_type": "department",
                "name": "Linked Department",
                "parent_id": first_school["id"],
            },
        )
    ).json()

    async with session_factory() as session:
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert administrator is not None
        administrator.college_id = UUID(first_college["id"])
        administrator.school_id = UUID(first_school["id"])
        administrator.department_id = UUID(department["id"])
        await session.commit()

    moved_department = await client.patch(
        f"/api/v1/organization/units/{department['id']}",
        headers=headers,
        json={"parent_id": second_school["id"]},
    )
    assert moved_department.status_code == 200

    async with session_factory() as session:
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert administrator is not None
        assert str(administrator.college_id) == second_college["id"]
        assert str(administrator.school_id) == second_school["id"]
        assert str(administrator.department_id) == department["id"]

    in_use = await client.delete(
        f"/api/v1/organization/units/{department['id']}",
        headers=headers,
    )
    assert in_use.status_code == 409
    assert in_use.json()["error"]["code"] == "organization_unit_in_use"


async def test_organization_rejects_inactive_or_invalid_parent_units(
    client: AsyncClient,
) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    college = (
        await client.post(
            "/api/v1/organization/units",
            headers=headers,
            json={"unit_type": "college", "name": "Inactive Parent College"},
        )
    ).json()
    school = (
        await client.post(
            "/api/v1/organization/units",
            headers=headers,
            json={
                "unit_type": "school",
                "name": "Active Child School",
                "parent_id": college["id"],
            },
        )
    ).json()
    active_child = await client.delete(
        f"/api/v1/organization/units/{college['id']}",
        headers=headers,
    )
    assert active_child.status_code == 409
    assert active_child.json()["error"]["code"] == "organization_unit_in_use"

    deactivated_school = await client.delete(
        f"/api/v1/organization/units/{school['id']}",
        headers=headers,
    )
    assert deactivated_school.status_code == 200
    deactivated = await client.delete(
        f"/api/v1/organization/units/{college['id']}",
        headers=headers,
    )
    assert deactivated.status_code == 200

    inactive_parent = await client.post(
        "/api/v1/organization/units",
        headers=headers,
        json={
            "unit_type": "school",
            "name": "School with Inactive Parent",
            "parent_id": college["id"],
        },
    )
    assert inactive_parent.status_code == 422
    assert inactive_parent.json()["error"]["code"] == "parent_unit_invalid"

    committee_with_parent = await client.post(
        "/api/v1/organization/units",
        headers=headers,
        json={
            "unit_type": "committee",
            "name": "Nested Committee",
            "parent_id": college["id"],
        },
    )
    assert committee_with_parent.status_code == 422
