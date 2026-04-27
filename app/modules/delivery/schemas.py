import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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
