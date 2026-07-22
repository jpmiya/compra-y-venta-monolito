import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Float, Integer, String, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Carrito(Base):
    __tablename__ = "carritos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # FK a Identidad — referencia por ID (sin constraint físico, cross-service)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    codigo_descuento: Mapped[Optional[str]] = mapped_column(String(50))
    descuento: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    items: Mapped[list["CarritoItem"]] = relationship(
        "CarritoItem", back_populates="carrito", cascade="all, delete-orphan"
    )


class CarritoItem(Base):
    __tablename__ = "carrito_items"
    __table_args__ = (UniqueConstraint("carrito_id", "producto_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    carrito_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("carritos.id"), nullable=False
    )
    # FK a Catálogo — referencia por ID (sin constraint físico, cross-service)
    producto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[float] = mapped_column(Float, nullable=False)

    carrito: Mapped["Carrito"] = relationship("Carrito", back_populates="items")


class SagaCheckout(Base):
    """Estado persistido de la saga de checkout (el orquestador vive acá).

    Transiciones:
      iniciada → stock_reservado → debitada (pivote ok) → stock_descontado → completada
      iniciada → fallida                      (ReservarStock rechazado — sin efectos)
      stock_reservado → compensada            (pivote falló → LiberarStock)
    """
    __tablename__ = "sagas_checkout"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    estado: Mapped[str] = mapped_column(
        SAEnum(
            "iniciada",
            "stock_reservado",
            "debitada",
            "stock_descontado",
            "completada",
            "compensada",
            "fallida",
            name="estado_saga_enum",
        ),
        nullable=False,
        default="iniciada",
    )
    total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    direccion_entrega: Mapped[str] = mapped_column(String(500), nullable=False)
    error: Mapped[Optional[str]] = mapped_column(String(500))
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class DeliveryLog(Base):
    """Log local de deliverys (outbox aplicado a delivery, plan §5.3/§9).

    El payload del CrearDeliveriesCmd se persiste ANTES de publicarlo: si el
    broker o Delivery están caídos, el worker de retry lo reenvía con el mismo
    message_id (Delivery es idempotente). `confirmado` lo marca la respuesta
    DeliveriesCreado recibida en el canal propio de la saga.
    """
    __tablename__ = "delivery_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    saga_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sagas_checkout.id"), nullable=False, unique=True
    )
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # CrearDeliveriesCmd serializado
    estado: Mapped[str] = mapped_column(
        SAEnum("pendiente_envio", "enviado", "confirmado", name="estado_delivery_log_enum"),
        nullable=False,
        default="pendiente_envio",
    )
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    fecha_confirmacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
