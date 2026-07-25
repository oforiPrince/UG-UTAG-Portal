from datetime import date

from utag_api.models import ExecutiveAppointment, User

EXECUTIVE_POSITION_ORDER = (
    "president",
    "vice president",
    "secretary",
    "treasurer",
    "women's executive officer",
    "national president",
    "cbas rep",
    "chs rep",
    "coe rep",
    "coh rep",
)
EXECUTIVE_OFFICER_POSITIONS = frozenset(EXECUTIVE_POSITION_ORDER[:5])

POSITION_ALIASES = {
    "college of humanities rep": "coh rep",
    "college of health rep": "chs rep",
    "college of education rep": "coe rep",
}

POSITION_ORDER_INDEX = {position: index for index, position in enumerate(EXECUTIVE_POSITION_ORDER)}


def normalize_executive_position(position: str) -> str:
    normalized = (
        position.replace("\u00a0", " ")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("-", " ")
        .casefold()
    )
    normalized = " ".join(normalized.split())
    return POSITION_ALIASES.get(normalized, normalized)


def executive_position_order_key(position: str) -> tuple[int, str]:
    normalized = normalize_executive_position(position)
    return POSITION_ORDER_INDEX.get(normalized, len(POSITION_ORDER_INDEX)), normalized


def is_executive_officer_position(position: str) -> bool:
    return normalize_executive_position(position) in EXECUTIVE_OFFICER_POSITIONS


def executive_row_order_key(
    appointment: ExecutiveAppointment,
    user: User,
) -> tuple[bool, int, str, int, str, str]:
    position_index, normalized_position = executive_position_order_key(appointment.position)
    appointed_on = appointment.appointed_on or date.min
    return (
        not appointment.is_active,
        position_index,
        normalized_position,
        -appointed_on.toordinal(),
        user.surname.casefold(),
        user.other_name.casefold(),
    )
