"""Contratos de Delivery para comunicación asincrónica vía RabbitMQ.

CrearDeliveriesCmd se publica en la cola de Delivery con canal de respuesta propio por saga_id.
DeliveriesCreado es el mensaje de confirmación que Delivery publica en el canal de respuesta.
"""
import uuid
from typing import List
from pydantic import BaseModel


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
    reply_queue: str           # canal de respuesta exclusivo para este saga_id
    items: List[DeliveryItemCmd]


class DeliveriesCreado(BaseModel):
    saga_id: uuid.UUID
    delivery_ids: List[uuid.UUID]
    ok: bool
