import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.core.database import Base


class DeliveryOrder(Base):
    __tablename__ = "delivery_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # FKs a Identidad / Catálogo — referencia por ID (sin constraint físico, cross-service)
    comprador_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    producto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[float] = mapped_column(Float, nullable=False)
    direccion_entrega: Mapped[str] = mapped_column(String(500), nullable=False)
    direccion_punto_venta_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entregador_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    estado: Mapped[str] = mapped_column(
        SAEnum("pendiente", "asignada", "entregada", name="estado_delivery_enum"),
        nullable=False,
        default="pendiente",
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    fecha_asignacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fecha_entrega: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class MensajeProcesado(Base):
    """Tabla de idempotencia: CrearDeliveries es reentregable (async con retry desde el log
    del orquestador), así que guarda los delivery_ids creados para devolver el mismo
    resultado ante una reentrega del mismo message_id."""
    __tablename__ = "mensajes_procesados"

    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    handler: Mapped[str] = mapped_column(String(100), nullable=False)
    delivery_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    procesado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
