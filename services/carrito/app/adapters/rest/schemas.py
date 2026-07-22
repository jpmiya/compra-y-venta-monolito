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


class CheckoutResponse(BaseModel):
    """El checkout ya no devuelve delivery_orders: los deliveries se crean
    asincrónicamente (post-pivote). El cliente puede consultar el estado
    de la saga en GET /carrito/checkout/{saga_id}."""
    saga_id: uuid.UUID
    estado: str
    total_cobrado: float
    saldo_restante: float
    moneda: str
    items_comprados: int


class SagaResponse(BaseModel):
    id: uuid.UUID
    usuario_id: uuid.UUID
    estado: str
    total: float
    direccion_entrega: str
    error: Optional[str]
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    delivery_estado: Optional[str] = None  # estado del log: pendiente_envio/enviado/confirmado

    model_config = {"from_attributes": True}


# --- Contratos inter-servicio (espejo de services/shared/contracts/delivery.py) ---

class DeliveryItemCmd(BaseModel):
    producto_id: uuid.UUID
    comprador_id: uuid.UUID
    cantidad: int
    precio_unitario: float
    direccion_entrega: str
    direccion_punto_venta_id: uuid.UUID


class CrearDeliveriesCmd(BaseModel):
    message_id: uuid.UUID
    saga_id: uuid.UUID
    reply_queue: str  # canal de respuesta exclusivo para este saga_id
    items: List[DeliveryItemCmd]


class DeliveriesCreado(BaseModel):
    saga_id: uuid.UUID
    delivery_ids: List[uuid.UUID]
    ok: bool
