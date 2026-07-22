import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.core.database import Base


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    imagen: Mapped[Optional[str]] = mapped_column(String(500))

    productos: Mapped[List["Producto"]] = relationship("Producto", back_populates="categoria")


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    precio: Mapped[float] = mapped_column(Float, nullable=False)
    categoria_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categorias.id"), nullable=False, index=True
    )
    # Stock físico total vs. reservado por sagas en curso.
    # Disponible = stock - stock_reservado (propiedad `stock_disponible`).
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock_reservado: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    imagenes: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    # FKs a Identidad — referencia por ID (sin constraint físico, cross-service)
    vendedor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    direccion_punto_venta_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    calificacion_promedio: Mapped[float] = mapped_column(Float, default=0.0)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    categoria: Mapped["Categoria"] = relationship("Categoria", back_populates="productos")
    resenas: Mapped[List["Resena"]] = relationship("Resena", back_populates="producto")

    @property
    def stock_disponible(self) -> int:
        return self.stock - self.stock_reservado


class Resena(Base):
    __tablename__ = "resenas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False, index=True
    )
    # FK a Identidad — referencia por ID (sin constraint físico, cross-service)
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    calificacion: Mapped[int] = mapped_column(Integer, nullable=False)
    comentario: Mapped[Optional[str]] = mapped_column(Text)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    producto: Mapped["Producto"] = relationship("Producto", back_populates="resenas")


class MensajeProcesado(Base):
    """Tabla de idempotencia: registra los message_id ya procesados por cada handler de stock."""
    __tablename__ = "mensajes_procesados"

    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    handler: Mapped[str] = mapped_column(String(100), nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(String(255))
    procesado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
