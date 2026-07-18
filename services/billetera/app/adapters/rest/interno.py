"""Endpoints internos — DebitarSaldo es el pivote de la saga, idempotente por message_id."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app import service
from app.adapters.rest.schemas import DebitarSaldoCmd, SaldoRespuesta

router = APIRouter(prefix="/interno", tags=["Interno"])


@router.post("/debitar", response_model=SaldoRespuesta)
async def debitar_saldo(
    cmd: DebitarSaldoCmd,
    db: AsyncSession = Depends(get_db),
):
    """
    Pivote de la saga de checkout. Idempotente: el mismo message_id siempre devuelve
    el mismo resultado sin debitar dos veces.
    Devuelve ok=False (no lanza excepción) cuando el saldo es insuficiente,
    para que el orquestador pueda disparar la compensación (LiberarStock).
    """
    ok, saldo_resultante, error = await service.debitar_saldo_idempotente(
        db,
        cmd.message_id,
        cmd.usuario_id,
        cmd.monto,
        cmd.descripcion,
    )
    return SaldoRespuesta(ok=ok, saldo_resultante=saldo_resultante, error=error)
