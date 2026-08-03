from datetime import UTC, datetime
from uuid import uuid4

from utag_api.schemas.domain import MemberView


def test_member_view_accepts_legacy_bootstrap_email() -> None:
    view = MemberView(
        id=uuid4(),
        email="bootstrap-admin@utag.local",
        staff_id="BOOTSTRAP",
        title="",
        other_name="Bootstrap",
        surname="Admin",
        gender=None,
        academic_rank=None,
        phone_number=None,
        school_id=None,
        college_id=None,
        department_id=None,
        full_name="Bootstrap Admin",
        status="active",
        email_verified=True,
        must_change_password=False,
        profile_media_id=None,
        roles=["administrator"],
        created_at=datetime.now(UTC),
        last_login_at=None,
    )

    assert view.email == "bootstrap-admin@utag.local"
