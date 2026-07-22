import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


class DeliveryOrderResponse(BaseModel):
    id: uuid.UUID
    comprador_id: uuid.UUID
    producto_id: uuid.UUID
    cantidad: int
    precio_unitario: float
    direccion_entrega: str
    direccion_punto_venta_id: uuid.UUID
    entregador_id: Optional[uuid.UUID]
    estado: str
    fecha_creacion: datetime
    fecha_asignacion: Optional[datetime]
    fecha_entrega: Optional[datetime]

    model_config = {"from_attributes": True}


# --- Contratos inter-servicio (CrearDeliveries — async vía RabbitMQ) ---
# Espejan services/shared/contracts/delivery.py (el build de Docker solo copia app/)

class DeliveryItemCmd(BaseModel):
    producto_id: uuid.UUID
    comprador_id: uuid.UUID
    cantidad: int
    precio_unitario: float
    direccion_entrega: str
    direccion_punto_venta_id: uuid.UUID

    @field_validator("cantidad")
    @classmethod
    def validate_cantidad(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("La cantidad debe ser positiva")
        return v


class CrearDeliveriesCmd(BaseModel):
    message_id: uuid.UUID
    saga_id: uuid.UUID
    reply_queue: str  # canal de respuesta exclusivo para este saga_id
    items: List[DeliveryItemCmd]


class DeliveriesCreado(BaseModel):
    saga_id: uuid.UUID
    delivery_ids: List[uuid.UUID]
    ok: bool
