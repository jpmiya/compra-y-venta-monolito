import firebase_admin
from firebase_admin import credentials, auth as firebase_auth

from app.core.config import settings

_initialized = False


def _init() -> None:
    global _initialized
    if not _initialized:
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        _initialized = True


def verify_firebase_token(token: str) -> dict:
    _init()
    return firebase_auth.verify_id_token(token)
