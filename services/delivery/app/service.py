import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.persistence.models import DeliveryOrder, MensajeProcesado
from app.adapters.rest.schemas import DeliveryItemCmd

logger = logging.getLogger(__name__)


async def listar_pendientes(db: AsyncSession) -> List[DeliveryOrder]:
    result = await db.execute(
        select(DeliveryOrder)
        .where(DeliveryOrder.estado == "pendiente")
        .order_by(DeliveryOrder.fecha_creacion.asc())
    )
    return result.scalars().all()


async def get_delivery_by_id(
    db: AsyncSession, delivery_id: uuid.UUID
) -> Optional[DeliveryOrder]:
    result = await db.execute(
        select(DeliveryOrder).where(DeliveryOrder.id == delivery_id)
    )
    return result.scalar_one_or_none()


async def listar_asignados(
    db: AsyncSession, entregador_id: uuid.UUID
) -> List[DeliveryOrder]:
    result = await db.execute(
        select(DeliveryOrder)
        .where(
            DeliveryOrder.entregador_id == entregador_id,
            DeliveryOrder.estado == "asignada",
        )
        .order_by(DeliveryOrder.fecha_asignacion.asc())
    )
    return result.scalars().all()


async def tomar_delivery(
    db: AsyncSession, delivery: DeliveryOrder, entregador_id: uuid.UUID
) -> DeliveryOrder:
    if delivery.estado != "pendiente":
        raise ValueError("Solo se puede tomar un delivery en estado pendiente")
    delivery.entregador_id = entregador_id
    delivery.estado = "asignada"
    delivery.fecha_asignacion = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(delivery)
    logger.info("DELIVERY TOMADO delivery=%s entregador=%s", delivery.id, entregador_id)
    return delivery


async def entregar(
    db: AsyncSession, delivery: DeliveryOrder, entregador_id: uuid.UUID
) -> DeliveryOrder:
    if delivery.estado != "asignada":
        raise ValueError("Solo se puede entregar un pedido en estado asignada")
    if delivery.entregador_id != entregador_id:
        raise ValueError("Solo el entregador asignado puede marcar el pedido como entregado")
    delivery.estado = "entregada"
    delivery.fecha_entrega = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(delivery)
    logger.info("DELIVERY ENTREGADO delivery=%s entregador=%s", delivery.id, entregador_id)
    return delivery


# --- Handler de la saga (asincrónico post-pivote, idempotente por message_id) ---

async def crear_deliveries_idempotente(
    db: AsyncSession, message_id: uuid.UUID, items: List[DeliveryItemCmd]
) -> Tuple[bool, List[uuid.UUID]]:
    """Crea un DeliveryOrder por ítem del checkout (igual que el monolito).

    Reentregable: el orquestador reintenta desde su log de deliverys, así que
    una reentrega del mismo message_id devuelve los MISMOS delivery_ids sin
    crear duplicados.
    """
    existing = await db.execute(
        select(MensajeProcesado).where(
            MensajeProcesado.message_id == message_id,
            MensajeProcesado.handler == "crear_deliveries",
        )
    )
    procesado = existing.scalar_one_or_none()
    if procesado:
        logger.info("CREAR DELIVERIES reentrega message_id=%s — resultado original", message_id)
        return True, list(procesado.delivery_ids)

    deliveries = [
        DeliveryOrder(
            comprador_id=item.comprador_id,
            producto_id=item.producto_id,
            cantidad=item.cantidad,
            precio_unitario=item.precio_unitario,
            direccion_entrega=item.direccion_entrega,
            direccion_punto_venta_id=item.direccion_punto_venta_id,
        )
        for item in items
    ]
    db.add_all(deliveries)
    await db.flush()  # asigna los IDs

    delivery_ids = [d.id for d in deliveries]
    db.add(
        MensajeProcesado(
            message_id=message_id,
            handler="crear_deliveries",
            delivery_ids=delivery_ids,
        )
    )
    await db.commit()
    logger.info("DELIVERIES CREADOS message_id=%s ids=%s", message_id, delivery_ids)
    return True, delivery_ids
