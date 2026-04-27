import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_active_user
from app.modules.delivery import service
from app.modules.delivery.schemas import DeliveryOrderResponse

router = APIRouter(prefix="/deliveries", tags=["Delivery"])


@router.get("", response_model=list[DeliveryOrderResponse])
async def listar_pendientes(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.listar_pendientes(db)


# declarado antes de /{delivery_id} para que FastAPI no confunda "mis-asignados" con un UUID
@router.get("/mis-asignados", response_model=list[DeliveryOrderResponse])
async def mis_asignados(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.listar_asignados(db, current_user.id)


@router.get("/{delivery_id}", response_model=DeliveryOrderResponse)
async def obtener_delivery(
    delivery_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    delivery = await service.get_delivery_by_id(db, delivery_id)
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery no encontrado")
    return delivery


@router.post("/{delivery_id}/tomar", response_model=DeliveryOrderResponse)
async def tomar_delivery(
    delivery_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    delivery = await service.get_delivery_by_id(db, delivery_id)
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery no encontrado")
    try:
        return await service.tomar_delivery(db, delivery, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{delivery_id}/entregar", response_model=DeliveryOrderResponse)
async def entregar(
    delivery_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    delivery = await service.get_delivery_by_id(db, delivery_id)
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery no encontrado")
    try:
        return await service.entregar(db, delivery, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
