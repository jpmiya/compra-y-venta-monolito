import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, field_validator


class AgregarItemRequest(BaseModel):
    producto_id: uuid.UUID
    cantidad: int

    @field_validator("cantidad")
    @classmethod
    def validate_cantidad(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        return v


class ModificarCantidadRequest(BaseModel):
    cantidad: int

    @field_validator("cantidad")
    @classmethod
    def validate_cantidad(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        return v


class AplicarDescuentoRequest(BaseModel):
    codigo: str


class CarritoItemResponse(BaseModel):
    producto_id: uuid.UUID
    cantidad: int
    precio_unitario: float
    subtotal: float


class CarritoResponse(BaseModel):
    id: uuid.UUID
    usuario_id: uuid.UUID
    items: List[CarritoItemResponse]
    subtotal: float
    descuento: float
    total: float
    codigo_descuento: Optional[str]
    fecha_creacion: datetime
