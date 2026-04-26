import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, Boolean, Integer
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(
        SAEnum(
            "orden_creada", "orden_actualizada", "password_reset", "bienvenida",
            name="tipo_notificacion_enum",
        ),
        nullable=False,
    )
    asunto: Mapped[str] = mapped_column(String(255), nullable=False)
    cuerpo: Mapped[str] = mapped_column(Text, nullable=False)
    enviada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    fecha_envio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
