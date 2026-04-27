import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel, field_validator


class BilleteraResponse(BaseModel):
    id: uuid.UUID
    usuario_id: uuid.UUID
    saldo: float
    moneda: str

    model_config = {"from_attributes": True}


class CargarSaldoRequest(BaseModel):
    monto: float

    @field_validator("monto")
    @classmethod
    def validate_monto(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("El monto debe ser positivo")
        return v


class TransaccionResponse(BaseModel):
    id: uuid.UUID
    billetera_id: uuid.UUID
    tipo: str
    monto: float
    descripcion: str
    fecha: datetime

    model_config = {"from_attributes": True}


class HistorialResponse(BaseModel):
    transacciones: List[TransaccionResponse]
    total: int
