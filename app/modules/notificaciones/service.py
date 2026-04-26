import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notificaciones.models import Notificacion

logger = logging.getLogger(__name__)


async def crear_notificacion(
    db: AsyncSession,
    usuario_id: uuid.UUID,
    tipo: str,
    asunto: str,
    cuerpo: str,
) -> Notificacion:
    notificacion = Notificacion(
        usuario_id=usuario_id,
        tipo=tipo,
        asunto=asunto,
        cuerpo=cuerpo,
    )
    db.add(notificacion)
    await db.flush()
    await _intentar_envio(db, notificacion)
    await db.commit()
    return notificacion


async def _intentar_envio(db: AsyncSession, notificacion: Notificacion) -> None:
    try:
        # TODO: integrar SMTP o SendGrid
        logger.info("[NOTIF] tipo=%s asunto=%s", notificacion.tipo, notificacion.asunto)
        notificacion.enviada = True
        notificacion.fecha_envio = datetime.now(timezone.utc)
    except Exception as exc:
        notificacion.intentos += 1
        logger.error("Error enviando notificación: %s", exc)


async def notificar_orden_creada(
    db: AsyncSession, usuario_id: uuid.UUID, numero_orden: str
) -> None:
    await crear_notificacion(
        db,
        usuario_id,
        "orden_creada",
        f"Orden {numero_orden} confirmada",
        f"Tu orden {numero_orden} fue recibida y está siendo procesada.",
    )


async def notificar_orden_actualizada(
    db: AsyncSession, usuario_id: uuid.UUID, numero_orden: str, nuevo_estado: str
) -> None:
    await crear_notificacion(
        db,
        usuario_id,
        "orden_actualizada",
        f"Actualización de orden {numero_orden}",
        f"El estado de tu orden {numero_orden} cambió a: {nuevo_estado}.",
    )
