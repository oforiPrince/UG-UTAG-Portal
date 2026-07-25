from sqlalchemy import func, select

from utag_api.demo_data import DEMO_ACCOUNTS, seed_demo_data
from utag_api.models import ExecutiveAppointment, Role, User, UserRole
from utag_api.security import verify_password


async def test_demo_seed_is_complete_login_ready_and_idempotent(session_factory, client) -> None:  # type: ignore[no-untyped-def]
    password = "".join(("Strong", "Demo", "Password", "2026!"))
    async with session_factory() as session:
        first = await seed_demo_data(session, password)
        second = await seed_demo_data(session, password)

        assert first == second
        assert first.accounts == len(DEMO_ACCOUNTS)
        assert first.executive_appointments == len(
            [account for account in DEMO_ACCOUNTS if account.executive_position]
        )

        users = {
            user.email: user
            for user in (
                await session.scalars(
                    select(User).where(User.email.in_([row.email for row in DEMO_ACCOUNTS]))
                )
            ).all()
        }
        assert len(users) == len(DEMO_ACCOUNTS)
        for account in DEMO_ACCOUNTS:
            user = users[account.email]
            assert user.status == "active"
            assert user.email_verified is True
            assert user.must_change_password is False
            assert user.college_id is not None
            assert user.school_id is not None
            assert user.department_id is not None
            assert verify_password(user.password_hash, password)[0] is True
            roles = set(
                (
                    await session.scalars(
                        select(Role.key)
                        .join(UserRole, UserRole.role_id == Role.id)
                        .where(UserRole.user_id == user.id)
                    )
                ).all()
            )
            assert roles == set(account.roles)

        assert (
            await session.scalar(
                select(func.count())
                .select_from(ExecutiveAppointment)
                .where(ExecutiveAppointment.user_id.in_([user.id for user in users.values()]))
            )
            == first.executive_appointments
        )

    public_leadership = await client.get("/api/v1/public/leadership")
    assert public_leadership.status_code == 200
    assert [row["position"] for row in public_leadership.json()[:10]] == [
        "President",
        "Vice President",
        "Secretary",
        "Treasurer",
        "Women's Executive Officer",
        "National President",
        "CBAS Rep",
        "CHS Rep",
        "COE Rep",
        "COH Rep",
    ]
    president = public_leadership.json()[0]
    assert president["email"] == "demo.executive@utag.com"
    assert president["phone_number"]
    assert president["department_name"]
    assert president["school_name"]
    assert president["college_name"]
    assert president["biography_html"]
    assert president["social_links"]["linkedin"]

    public_home = await client.get("/api/v1/public/home")
    assert public_home.status_code == 200
    assert [row["position"] for row in public_home.json()["leadership"]] == [
        "President",
        "Vice President",
        "Secretary",
        "Treasurer",
        "Women's Executive Officer",
    ]
