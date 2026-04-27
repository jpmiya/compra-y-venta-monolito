import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.billetera.models import BilleteraVirtual, TransaccionBilletera


async def get_or_create_billetera(
    db: AsyncSession, usuario_id: uuid.UUID
) -> BilleteraVirtual:
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


async def cargar_saldo(
    db: AsyncSession, billetera: BilleteraVirtual, monto: float
) -> BilleteraVirtual:
    if monto > settings.BILLETERA_LIMITE_CARGA:
        raise ValueError(
            f"El monto supera el límite de carga permitido ({settings.BILLETERA_LIMITE_CARGA} {billetera.moneda})"
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


async def descontar_saldo(
    db: AsyncSession, billetera: BilleteraVirtual, monto: float, descripcion: str
) -> BilleteraVirtual:
    if billetera.saldo < monto:
        raise ValueError("Saldo insuficiente en la billetera")
    billetera.saldo -= monto
    transaccion = TransaccionBilletera(
        billetera_id=billetera.id,
        tipo="compra",
        monto=monto,
        descripcion=descripcion,
    )
    db.add(transaccion)
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
