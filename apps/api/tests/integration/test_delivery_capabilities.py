from types import SimpleNamespace
from uuid import UUID

import pytest
from httpx import AsyncClient

from utag_api.errors import ApiError
from utag_api.models import User
from utag_api.security import hash_password
from utag_api.services.delivery import (
    delivery_available,
    email_delivery_enabled,
    public_capabilities,
    require_email_delivery,
    sms_delivery_enabled,
)


def test_capabilities_reflect_smtp_configuration() -> None:
    assert public_capabilities(
        SimpleNamespace(
            smtp_host="smtp.example.org",
            smtp_username="utag@example.org",
            smtp_password=SimpleNamespace(get_secret_value=lambda: "secret"),
        )
    ) == {
        "email_delivery": True,
        "sms_delivery": False,
    }
    assert public_capabilities(
        SimpleNamespace(smtp_host=None, smtp_username=None, smtp_password=None)
    ) == {
        "email_delivery": False,
        "sms_delivery": False,
    }
    assert public_capabilities(
        SimpleNamespace(
            smtp_host="smtp.gmail.com",
            smtp_username="",
            smtp_password=SimpleNamespace(get_secret_value=lambda: ""),
        )
    ) == {
        "email_delivery": False,
        "sms_delivery": False,
    }
    assert email_delivery_enabled(
        SimpleNamespace(
            smtp_host="smtp.example.org",
            smtp_username="utag@example.org",
            smtp_password=SimpleNamespace(get_secret_value=lambda: "secret"),
        )
    )
    assert not email_delivery_enabled(
        SimpleNamespace(smtp_host=None, smtp_username=None, smtp_password=None)
    )
    assert not email_delivery_enabled(
        SimpleNamespace(
            smtp_host="smtp.gmail.com",
            smtp_username="",
            smtp_password=SimpleNamespace(get_secret_value=lambda: ""),
        )
    )
    assert email_delivery_enabled(
        SimpleNamespace(
            smtp_host="relay.ug.edu.gh",
            smtp_auth_required=False,
            smtp_username=None,
            smtp_password=None,
        )
    )
    assert not sms_delivery_enabled(SimpleNamespace(smtp_host="smtp.example.org"))
    assert delivery_available(
        SimpleNamespace(
            smtp_host="smtp.example.org",
            smtp_username="utag@example.org",
            smtp_password=SimpleNamespace(get_secret_value=lambda: "secret"),
        )
    )
    assert not delivery_available(
        SimpleNamespace(smtp_host=None, smtp_username=None, smtp_password=None)
    )


def test_require_email_delivery_raises_when_disabled(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "utag_api.services.delivery.get_settings",
        lambda: SimpleNamespace(smtp_host=None, smtp_username=None, smtp_password=None),
    )
    with pytest.raises(ApiError) as raised:
        require_email_delivery()
    assert raised.value.status_code == 503
    assert raised.value.code == "email_delivery_disabled"


async def test_public_capabilities_endpoint(
    client: AsyncClient, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "utag_api.services.delivery.get_settings",
        lambda: SimpleNamespace(
            smtp_host="smtp.example.org",
            smtp_username="utag@example.org",
            smtp_password=SimpleNamespace(get_secret_value=lambda: "secret"),
        ),
    )
    response = await client.get("/api/v1/public/capabilities")
    assert response.status_code == 200
    assert response.json() == {"email_delivery": True, "sms_delivery": False}

    monkeypatch.setattr(
        "utag_api.services.delivery.get_settings",
        lambda: SimpleNamespace(smtp_host=None, smtp_username=None, smtp_password=None),
    )
    disabled = await client.get("/api/v1/public/capabilities")
    assert disabled.status_code == 200
    assert disabled.json() == {"email_delivery": False, "sms_delivery": False}


async def test_forgot_password_and_credential_actions_require_email(
    client: AsyncClient, monkeypatch, session_factory
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "utag_api.services.delivery.get_settings",
        lambda: SimpleNamespace(smtp_host=None, smtp_username=None, smtp_password=None),
    )
    forgot = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "admin@example.edu.gh"},
    )
    assert forgot.status_code == 503
    assert forgot.json()["error"]["code"] == "email_delivery_disabled"

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    created = await client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "email": "temp.pass@example.edu.gh",
            "staff_id": "UGTEMP01",
            "title": "Dr.",
            "other_name": "Kojo",
            "surname": "Mensah",
            "roles": ["member"],
            "send_invitation": True,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "active"
    assert body["must_change_password"] is True
    member_id = body["id"]

    access = await client.post(
        f"/api/v1/members/{member_id}/access-link",
        headers=headers,
    )
    assert access.status_code == 503

    # Change the password away from staff ID, then reset without email.
    async with session_factory() as session:
        member = await session.get(User, UUID(member_id))
        assert member is not None
        member.password_hash = hash_password("ChangedPass123!")
        member.must_change_password = False
        member.email_verified = True
        await session.commit()

    reset = await client.post(
        f"/api/v1/members/{member_id}/password-reset",
        headers=headers,
    )
    assert reset.status_code == 200
    assert "staff ID" in reset.json()["message"]

    signed_in = await client.post(
        "/api/v1/auth/login",
        json={"email": "temp.pass@example.edu.gh", "password": "UGTEMP01"},
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["user"]["must_change_password"] is True

    old_password = await client.post(
        "/api/v1/auth/login",
        json={"email": "temp.pass@example.edu.gh", "password": "ChangedPass123!"},
    )
    assert old_password.status_code == 401

    # Unverified active members can still be force-reset by an administrator.
    async with session_factory() as session:
        member = await session.get(User, UUID(member_id))
        assert member is not None
        member.password_hash = hash_password("AnotherPass123!")
        member.must_change_password = False
        member.email_verified = False
        await session.commit()

    # The temporary-member login above replaced the test client's session cookie.
    # Restore the administrator identity before exercising an administrator action.
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    assert admin_login.status_code == 200
    headers = {"X-CSRF-Token": admin_login.json()["csrf_token"]}

    unverified_reset = await client.post(
        f"/api/v1/members/{member_id}/password-reset",
        headers=headers,
    )
    assert unverified_reset.status_code == 200
    assert "staff ID" in unverified_reset.json()["message"]

    unverified_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "temp.pass@example.edu.gh", "password": "UGTEMP01"},
    )
    assert unverified_login.status_code == 200
    assert unverified_login.json()["user"]["must_change_password"] is True


async def test_create_member_without_staff_id_fails_when_email_off(
    client: AsyncClient, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "utag_api.services.delivery.get_settings",
        lambda: SimpleNamespace(smtp_host=None, smtp_username=None, smtp_password=None),
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    created = await client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "email": "missing.staff@example.edu.gh",
            "title": "Dr.",
            "other_name": "Ama",
            "surname": "Boateng",
            "roles": ["member"],
            "send_invitation": False,
        },
    )
    assert created.status_code == 422
    assert created.json()["error"]["code"] == "staff_id_required"
