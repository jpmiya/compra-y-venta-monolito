"""Cliente HTTP para llamadas sincrónicas a Identidad.

Se usa para:
- Resolver el usuario autenticado desde el firebase_uid (guard de auth).
- Validar que la dirección del punto de venta pertenece al vendedor (crear producto).
- Composición síncrona en lectura: resolver las direcciones de punto de venta
  al servir listados/búsqueda (batch por IDs únicos).
"""
import uuid
from typing import List, Optional

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

    async def get_direccion(self, direccion_id: uuid.UUID) -> Optional[dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/interno/direcciones/{direccion_id}",
                timeout=5.0,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def get_direcciones(self, direccion_ids: List[uuid.UUID]) -> List[dict]:
        """Batch: una sola llamada por listado, con los IDs únicos de dirección."""
        if not direccion_ids:
            return []
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/interno/direcciones",
                params=[("ids", str(d)) for d in direccion_ids],
                timeout=5.0,
            )
            response.raise_for_status()
            return response.json()


def get_identidad_client() -> IdentidadClient:
    return IdentidadClient()
