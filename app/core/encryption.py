import base64
import hashlib
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import String, TypeDecorator


class EncryptionService:
    """
    Cifrado AES-256-GCM con nonce determinístico derivado de HMAC(key, plaintext).
    Determinístico: el mismo texto siempre produce el mismo ciphertext con la misma clave,
    lo que permite comparaciones de igualdad en SQL (WHERE email = ?).
    """

    def __init__(self, key_b64: str) -> None:
        raw = base64.urlsafe_b64decode(key_b64.encode() + b"==")
        self.key = raw[:32]
        self.aesgcm = AESGCM(self.key)

    def encrypt(self, plaintext: str) -> str:
        nonce = hashlib.sha256(self.key + plaintext.encode()).digest()[:12]
        ct = self.aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.urlsafe_b64encode(nonce + ct).decode()

    def decrypt(self, ciphertext: str) -> str:
        data = base64.urlsafe_b64decode(ciphertext.encode() + b"==")
        nonce, ct = data[:12], data[12:]
        return self.aesgcm.decrypt(nonce, ct, None).decode()


_service: Optional[EncryptionService] = None


def get_encryption_service() -> Optional[EncryptionService]:
    global _service
    if _service is None:
        from app.core.config import settings
        if settings.ENCRYPTION_KEY:
            _service = EncryptionService(settings.ENCRYPTION_KEY)
    return _service


class EncryptedString(TypeDecorator):
    """TypeDecorator que cifra/descifra transparentemente al leer y escribir en BD."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        if value is None:
            return None
        svc = get_encryption_service()
        return svc.encrypt(value) if svc else value

    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        if value is None:
            return None
        svc = get_encryption_service()
        if not svc:
            return value
        try:
            return svc.decrypt(value)
        except Exception:
            return value
