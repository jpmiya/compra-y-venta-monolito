"""Contratos de Billetera para comunicación inter-servicio (REST síncrono).

DebitarSaldoCmd es idempotente por message_id — el orquestador puede reintentar sin debitar dos veces.
"""
import uuid
from typing import Optional
from pydantic import BaseModel


class DebitarSaldoCmd(BaseModel):
    message_id: uuid.UUID
    usuario_id: uuid.UUID
    monto: float
    descripcion: str


class SaldoRespuesta(BaseModel):
    ok: bool
    saldo_resultante: float
    error: Optional[str] = None
