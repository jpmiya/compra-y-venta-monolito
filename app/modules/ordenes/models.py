import uuid
from datetime import datetime

from sqlalchemy import Float, Integer, String, DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Orden(Base):
    __tablename__ = "ordenes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero_orden: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False, index=True
    )
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)
    impuesto: Mapped[float] = mapped_column(Float, nullable=False)
    descuento: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total: Mapped[float] = mapped_column(Float, nullable=False)
    estado: Mapped[str] = mapped_column(
        SAEnum(
            "pendiente", "pagada", "procesando", "enviada", "entregada", "cancelada",
            name="estado_orden_enum",
        ),
        nullable=False,
        default="pendiente",
    )
    direccion_entrega: Mapped[str] = mapped_column(String(255), nullable=False)
    telefono_contacto: Mapped[str] = mapped_column(String(20), nullable=False)
    numero_seguimiento: Mapped[str | None] = mapped_column(String(100))
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    items: Mapped[list["OrdenItem"]] = relationship(
        "OrdenItem", back_populates="orden", cascade="all, delete-orphan"
    )


class OrdenItem(Base):
    __tablename__ = "orden_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orden_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ordenes.id"), nullable=False
    )
    producto_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False
    )
    nombre_producto: Mapped[str] = mapped_column(String(255), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[float] = mapped_column(Float, nullable=False)

    orden: Mapped["Orden"] = relationship("Orden", back_populates="items")
