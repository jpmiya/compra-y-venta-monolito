"""Contratos de Catálogo para comunicación inter-servicio (REST síncrono).

ReservarStock y DescontarStock son idempotentes por message_id.
LiberarStock es la compensación de ReservarStock.
"""
import uuid
from typing import Optional, List
from pydantic import BaseModel


class ItemStockCmd(BaseModel):
    producto_id: uuid.UUID
    cantidad: int


class ReservarStockCmd(BaseModel):
    message_id: uuid.UUID
    saga_id: uuid.UUID
    items: List[ItemStockCmd]


class DescontarStockCmd(BaseModel):
    message_id: uuid.UUID
    saga_id: uuid.UUID
    items: List[ItemStockCmd]


class LiberarStockCmd(BaseModel):
    message_id: uuid.UUID
    saga_id: uuid.UUID
    items: List[ItemStockCmd]


class StockRespuesta(BaseModel):
    ok: bool
    error: Optional[str] = None
