from httpx import AsyncClient


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
