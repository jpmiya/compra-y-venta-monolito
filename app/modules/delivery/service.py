import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.delivery.models import DeliveryOrder

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
