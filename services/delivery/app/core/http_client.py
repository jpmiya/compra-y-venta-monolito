"""Cliente HTTP para llamadas sincrónicas a Identidad (para resolver usuario_id desde firebase_uid)."""
import uuid
from typing import Optional

import httpx

from app.core.config import settings


class IdentidadClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.IDENTIDAD_SERVICE_URL

    async def get_usuario_by_firebase_uid(self, firebase_uid: str) -> Optional[dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/interno/usuarios/by-firebase/{firebase_uid}",
                timeout=5.0,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()


def get_identidad_client() -> IdentidadClient:
    return IdentidadClient()
