import uuid
from datetime import datetime

from sqlalchemy import Float, String, DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class BilleteraVirtual(Base):
    __tablename__ = "billeteras"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False, unique=True
    )
    saldo: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    moneda: Mapped[str] = mapped_column(String(10), nullable=False, default="ARS")

    transacciones: Mapped[list["TransaccionBilletera"]] = relationship(
        "TransaccionBilletera", back_populates="billetera", cascade="all, delete-orphan"
    )


class TransaccionBilletera(Base):
    __tablename__ = "transacciones_billetera"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    billetera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billeteras.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(
        SAEnum("carga", "compra", name="tipo_transaccion_enum"),
        nullable=False,
    )
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    billetera: Mapped["BilleteraVirtual"] = relationship(
        "BilleteraVirtual", back_populates="transacciones"
    )
