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


class CheckoutRequest(BaseModel):
    direccion_entrega: str

    @field_validator("direccion_entrega")
    @classmethod
    def validate_direccion(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("La dirección de entrega no puede estar vacía")
        return v


class CheckoutDeliveryItem(BaseModel):
    id: uuid.UUID
    producto_id: uuid.UUID
    cantidad: int
    precio_unitario: float
    direccion_entrega: str
    estado: str

    model_config = {"from_attributes": True}


class CheckoutResponse(BaseModel):
    delivery_orders: List[CheckoutDeliveryItem]
    total_cobrado: float
    moneda: str
