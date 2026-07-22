"""Clientes HTTP para los pasos sincrónicos de la saga (plan §9).

- IdentidadClient: resolver el usuario autenticado (guard de auth).
- CatalogoClient: consulta de producto + comandos ReservarStock/DescontarStock/LiberarStock.
- BilleteraClient: DebitarSaldo (el pivote).

Todos los comandos viajan con message_id: los participantes son idempotentes.
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


def get_identidad_client() -> IdentidadClient:
    return IdentidadClient()


class CatalogoClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.CATALOGO_SERVICE_URL

    async def get_producto(self, producto_id: uuid.UUID) -> Optional[dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/interno/productos/{producto_id}", timeout=5.0
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def _comando_stock(
        self, accion: str, message_id: uuid.UUID, saga_id: uuid.UUID, items: List[dict]
    ) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/interno/stock/{accion}",
                json={
                    "message_id": str(message_id),
                    "saga_id": str(saga_id),
                    "items": items,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()  # {"ok": bool, "error": str|None}

    async def reservar_stock(self, message_id, saga_id, items) -> dict:
        return await self._comando_stock("reservar", message_id, saga_id, items)

    async def descontar_stock(self, message_id, saga_id, items) -> dict:
        return await self._comando_stock("descontar", message_id, saga_id, items)

    async def liberar_stock(self, message_id, saga_id, items) -> dict:
        return await self._comando_stock("liberar", message_id, saga_id, items)


def get_catalogo_client() -> CatalogoClient:
    return CatalogoClient()


class BilleteraClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.BILLETERA_SERVICE_URL

    async def debitar_saldo(
        self, message_id: uuid.UUID, usuario_id: uuid.UUID, monto: float, descripcion: str
    ) -> dict:
        """Pivote de la saga. Devuelve {"ok": bool, "saldo_resultante": float, "error": str|None}."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/interno/debitar",
                json={
                    "message_id": str(message_id),
                    "usuario_id": str(usuario_id),
                    "monto": monto,
                    "descripcion": descripcion,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()


def get_billetera_client() -> BilleteraClient:
    return BilleteraClient()
