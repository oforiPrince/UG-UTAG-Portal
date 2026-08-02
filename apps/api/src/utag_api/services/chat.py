import hashlib
from uuid import UUID

from cryptography.fernet import Fernet

from utag_api.config import get_settings
from utag_api.security import field_cipher


def direct_conversation_key(user_ids: list[UUID]) -> str:
    normalized = ":".join(sorted(str(user_id) for user_id in user_ids))
    return hashlib.sha256(normalized.encode()).hexdigest()


def new_conversation_key() -> tuple[bytes, str]:
    raw = Fernet.generate_key()
    encrypted = field_cipher().encrypt(raw)
    return encrypted, get_settings().field_encryption_key_version


def encrypt_message(conversation_key: bytes, text: str) -> bytes:
    raw_key = field_cipher().decrypt(conversation_key)
    return Fernet(raw_key).encrypt(text.encode())


def decrypt_message(conversation_key: bytes, ciphertext: bytes) -> str:
    raw_key = field_cipher().decrypt(conversation_key)
    return Fernet(raw_key).decrypt(ciphertext).decode()
