import base64
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet

from utag_api.config import get_settings

password_hasher = PasswordHasher(time_cost=3, memory_cost=65_536, parallelism=4)


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def _verify_django_pbkdf2(password_hash: str, password: str) -> bool:
    try:
        algorithm, iterations_text, salt, encoded = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations_text)
        )
        return hmac.compare_digest(base64.b64encode(derived).decode(), encoded)
    except (ValueError, TypeError):
        return False


def verify_password(password_hash: str, password: str) -> tuple[bool, bool]:
    """Return whether the password matches and whether the hash should be upgraded."""
    if password_hash.startswith("pbkdf2_sha256$"):
        return _verify_django_pbkdf2(password_hash, password), True
    try:
        valid = password_hasher.verify(password_hash, password)
        return valid, valid and password_hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False, False


def new_token() -> str:
    return secrets.token_urlsafe(48)


def token_digest(value: str) -> str:
    secret = get_settings().app_secret_key.get_secret_value().encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())


def field_cipher() -> Fernet:
    secret = get_settings().app_secret_key.get_secret_value().encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(b"ug-utag-fields:" + secret).digest())
    return Fernet(key)


def encrypt_text(value: str | None) -> bytes | None:
    return field_cipher().encrypt(value.encode()) if value else None


def decrypt_text(value: bytes | None) -> str | None:
    return field_cipher().decrypt(value).decode() if value else None
