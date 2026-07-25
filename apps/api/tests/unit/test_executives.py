from utag_api.services.executives import (
    executive_position_order_key,
    is_executive_officer_position,
    normalize_executive_position,
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
