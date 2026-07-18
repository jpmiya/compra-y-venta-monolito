import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.adapters.persistence.models import BilleteraVirtual, TransaccionBilletera, MensajeProcesado


async def get_or_create_billetera(db: AsyncSession, usuario_id: uuid.UUID) -> BilleteraVirtual:
    result = await db.execute(
        select(BilleteraVirtual).where(BilleteraVirtual.usuario_id == usuario_id)
    )
    billetera = result.scalar_one_or_none()
    if not billetera:
        billetera = BilleteraVirtual(
            usuario_id=usuario_id,
            moneda=settings.BILLETERA_MONEDA,
        )
        db.add(billetera)
        await db.commit()
        await db.refresh(billetera)
    return billetera


async def cargar_saldo(db: AsyncSession, billetera: BilleteraVirtual, monto: float) -> BilleteraVirtual:
    if monto > settings.BILLETERA_LIMITE_CARGA:
        raise ValueError(
            f"El monto supera el límite permitido de {settings.BILLETERA_LIMITE_CARGA}"
        )
    billetera.saldo += monto
    transaccion = TransaccionBilletera(
        billetera_id=billetera.id,
        tipo="carga",
        monto=monto,
        descripcion=f"Carga de saldo: +{monto} {billetera.moneda}",
    )
    db.add(transaccion)
    await db.commit()
    await db.refresh(billetera)
    return billetera


async def listar_transacciones(
    db: AsyncSession, billetera_id: uuid.UUID
) -> List[TransaccionBilletera]:
    result = await db.execute(
        select(TransaccionBilletera)
        .where(TransaccionBilletera.billetera_id == billetera_id)
        .order_by(TransaccionBilletera.fecha.desc())
    )
    return result.scalars().all()


async def debitar_saldo_idempotente(
    db: AsyncSession,
    message_id: uuid.UUID,
    usuario_id: uuid.UUID,
    monto: float,
    descripcion: str,
) -> tuple[bool, float, Optional[str]]:
    """
    Debita saldo de forma idempotente usando message_id.
    Retorna (ok, saldo_resultante, error).
    Si el message_id ya fue procesado, devuelve el resultado original sin debitar de nuevo.
    """
    # Chequeo de idempotencia
    existing = await db.execute(
        select(MensajeProcesado).where(
            MensajeProcesado.message_id == message_id,
            MensajeProcesado.handler == "debitar_saldo",
        )
    )
    procesado = existing.scalar_one_or_none()
    if procesado:
        return True, procesado.saldo_resultante, None

    billetera = await get_or_create_billetera(db, usuario_id)

    if billetera.saldo < monto:
        return False, billetera.saldo, "Saldo insuficiente en la billetera"

    billetera.saldo -= monto
    transaccion = TransaccionBilletera(
        billetera_id=billetera.id,
        tipo="compra",
        monto=monto,
        descripcion=descripcion,
    )
    db.add(transaccion)

    # Registrar idempotencia en la misma transacción DB
    registro = MensajeProcesado(
        message_id=message_id,
        handler="debitar_saldo",
        saldo_resultante=billetera.saldo,
    )
    db.add(registro)

    await db.commit()
    await db.refresh(billetera)
    return True, billetera.saldo, None
