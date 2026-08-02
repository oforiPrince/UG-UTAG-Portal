from utag_api.services.executives import (
    biography_is_complete,
    executive_position_order_key,
    executive_public_profile_incomplete,
    is_executive_officer_position,
    normalize_executive_position,
    plain_text_from_html,
)


def test_executive_positions_follow_the_legacy_public_precedence() -> None:
    positions = [
        "COH Rep",
        "Treasurer",
        "President",
        "National President",
        "Vice President",
        "Women's Executive Officer",
        "Secretary",
        "CBAS Rep",
        "CHS Rep",
        "COE Rep",
    ]
    assert sorted(positions, key=executive_position_order_key) == [
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


def test_executive_position_order_normalizes_legacy_variants() -> None:
    assert normalize_executive_position("Women\u2019s Executive\u00a0Officer") == (
        "women's executive officer"
    )
    assert normalize_executive_position("Vice-President") == "vice president"
    assert normalize_executive_position("College of Humanities Rep") == "coh rep"


def test_new_positions_follow_known_positions_in_readable_order() -> None:
    positions = ["Organiser", "Assistant Secretary", "President", "Past President"]
    assert sorted(positions, key=executive_position_order_key) == [
        "President",
        "Assistant Secretary",
        "Organiser",
        "Past President",
    ]


def test_only_the_five_legacy_branch_offices_are_executive_officers() -> None:
    assert is_executive_officer_position("President") is True
    assert is_executive_officer_position("Women\u2019s Executive Officer") is True
    assert is_executive_officer_position("Assistant Secretary") is False
    assert is_executive_officer_position("CBAS Rep") is False


def test_public_biography_requires_meaningful_plain_text() -> None:
    assert plain_text_from_html("<p>Serving <strong>UG UTAG</strong> members.</p>") == (
        "Serving UG UTAG members."
    )
    assert biography_is_complete("<p>Too short</p>") is False
    assert biography_is_complete(
        "<p>Serving members across the University of Ghana campus.</p>"
    )


def test_active_public_appointments_require_photo_and_biography() -> None:
    class _User:
        profile_media_id = None

    class _Appointment:
        is_active = True
        is_public = True
        biography_html = ""

    user = _User()
    appointment = _Appointment()
    assert executive_public_profile_incomplete(user, appointment) is True

    user.profile_media_id = "photo-id"
    appointment.biography_html = (
        "<p>Serving members across the University of Ghana campus.</p>"
    )
    assert executive_public_profile_incomplete(user, appointment) is False

    appointment.is_public = False
    appointment.biography_html = ""
    assert executive_public_profile_incomplete(user, appointment) is False
