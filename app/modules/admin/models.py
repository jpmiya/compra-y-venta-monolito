import uuid
from datetime import datetime, date
from typing import List

from sqlalchemy import String, DateTime, Date, Boolean, ForeignKey, Table, Column
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

usuario_roles = Table(
    "usuario_roles",
    Base.metadata,
    Column("usuario_id", UUID(as_uuid=True), ForeignKey("usuarios.id"), primary_key=True),
    Column("rol_id", UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
)


class Rol(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    usuarios: Mapped[List["Usuario"]] = relationship(
        "Usuario", secondary=usuario_roles, back_populates="roles"
    )


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_completo: Mapped[str] = mapped_column(String(200), nullable=False)
    documento_identidad: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    telefono: Mapped[str | None] = mapped_column(String(20))
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    estado: Mapped[str] = mapped_column(
        SAEnum("activo", "inactivo", name="estado_persona_enum"),
        nullable=False,
        default="activo",
    )

    usuarios: Mapped[List["Usuario"]] = relationship("Usuario", back_populates="persona")
    direcciones: Mapped[List["Direccion"]] = relationship("Direccion", back_populates="persona")


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    firebase_uid: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    fecha_ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(
        SAEnum("activo", "inactivo", name="estado_usuario_enum"),
        nullable=False,
        default="activo",
    )

    persona: Mapped["Persona"] = relationship("Persona", back_populates="usuarios")
    roles: Mapped[List["Rol"]] = relationship(
        "Rol", secondary=usuario_roles, back_populates="usuarios"
    )


class Direccion(Base):
    __tablename__ = "direcciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id"), nullable=False
    )
    calle: Mapped[str] = mapped_column(String(200), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(100), nullable=False)
    provincia: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(200))
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    persona: Mapped["Persona"] = relationship("Persona", back_populates="direcciones")
