import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_usuario_id
from app import service
from app.adapters.rest.schemas import DeliveryOrderResponse

router = APIRouter(prefix="/deliveries", tags=["Delivery"])


@router.get("", response_model=list[DeliveryOrderResponse])
async def listar_pendientes(
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
):
    return await service.listar_pendientes(db)


# declarado antes de /{delivery_id} para que FastAPI no confunda "mis-asignados" con un UUID
@router.get("/mis-asignados", response_model=list[DeliveryOrderResponse])
async def mis_asignados(
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
):
    return await service.listar_asignados(db, usuario_id)


@router.get("/{delivery_id}", response_model=DeliveryOrderResponse)
async def obtener_delivery(
    delivery_id: uuid.UUID,
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
):
    delivery = await service.get_delivery_by_id(db, delivery_id)
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery no encontrado")
    return delivery


@router.post("/{delivery_id}/tomar", response_model=DeliveryOrderResponse)
async def tomar_delivery(
    delivery_id: uuid.UUID,
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
):
    delivery = await service.get_delivery_by_id(db, delivery_id)
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery no encontrado")
    try:
        return await service.tomar_delivery(db, delivery, usuario_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{delivery_id}/entregar", response_model=DeliveryOrderResponse)
async def entregar(
    delivery_id: uuid.UUID,
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
):
    delivery = await service.get_delivery_by_id(db, delivery_id)
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery no encontrado")
    try:
        return await service.entregar(db, delivery, usuario_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
