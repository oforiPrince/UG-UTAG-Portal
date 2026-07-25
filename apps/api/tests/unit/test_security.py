import base64
import hashlib

from utag_api.security import hash_password, verify_password


def test_argon2_password_round_trip() -> None:
    password_hash = hash_password("A-Much-Stronger-Password-123")
    valid, upgrade = verify_password(password_hash, "A-Much-Stronger-Password-123")
    assert valid is True
    assert upgrade is False


def test_django_pbkdf2_hash_is_verified_and_marked_for_upgrade() -> None:
    password = "".join(("Legacy", "Password", "123"))
    salt = "legacy-salt"
    iterations = 390_000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    password_hash = f"pbkdf2_sha256${iterations}${salt}${base64.b64encode(derived).decode()}"
    valid, upgrade = verify_password(password_hash, password)
    assert valid is True
    assert upgrade is True
