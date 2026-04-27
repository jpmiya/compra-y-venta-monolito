from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_active_user
from app.modules.billetera import service
from app.modules.billetera.schemas import (
    BilleteraResponse,
    CargarSaldoRequest,
    HistorialResponse,
    TransaccionResponse,
)

router = APIRouter(prefix="/billetera", tags=["Billetera Virtual"])


@router.get("", response_model=BilleteraResponse)
async def obtener_billetera(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    billetera = await service.get_or_create_billetera(db, current_user.id)
    return billetera


@router.post("/cargar", response_model=BilleteraResponse)
async def cargar_saldo(
    data: CargarSaldoRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    billetera = await service.get_or_create_billetera(db, current_user.id)
    try:
        return await service.cargar_saldo(db, billetera, data.monto)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/historial", response_model=HistorialResponse)
async def obtener_historial(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    billetera = await service.get_or_create_billetera(db, current_user.id)
    transacciones = await service.listar_transacciones(db, billetera.id)
    return {"transacciones": transacciones, "total": len(transacciones)}
