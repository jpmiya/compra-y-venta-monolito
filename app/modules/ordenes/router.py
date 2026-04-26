import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_active_user
from app.modules.ordenes import service
from app.modules.ordenes.schemas import (
    CrearOrdenRequest,
    ActualizarEstadoRequest,
    OrdenResponse,
    SeguimientoResponse,
)

router = APIRouter(prefix="/ordenes", tags=["Órdenes"])


@router.post("", response_model=OrdenResponse, status_code=status.HTTP_201_CREATED)
async def crear_orden(
    data: CrearOrdenRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.crear_orden(db, current_user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[OrdenResponse])
async def listar_ordenes(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.listar_ordenes(db, current_user.id)


@router.get("/{orden_id}", response_model=OrdenResponse)
async def obtener_orden(
    orden_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    orden = await service.get_orden_by_id(db, orden_id)
    if not orden:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")
    if str(orden.usuario_id) != str(current_user.id) and current_user.rol != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")
    return orden


@router.put("/{orden_id}/estado", response_model=OrdenResponse)
async def actualizar_estado(
    orden_id: uuid.UUID,
    data: ActualizarEstadoRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    orden = await service.get_orden_by_id(db, orden_id)
    if not orden:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")
    try:
        return await service.actualizar_estado(db, orden, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{orden_id}/cancelar", response_model=OrdenResponse)
async def cancelar_orden(
    orden_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    orden = await service.get_orden_by_id(db, orden_id)
    if not orden:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")
    try:
        return await service.cancelar_orden(db, orden, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{orden_id}/seguimiento", response_model=SeguimientoResponse)
async def obtener_seguimiento(
    orden_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    orden = await service.get_orden_by_id(db, orden_id)
    if not orden:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")
    if str(orden.usuario_id) != str(current_user.id) and current_user.rol != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")
    return orden
