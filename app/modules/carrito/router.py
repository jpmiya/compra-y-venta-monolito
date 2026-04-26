import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_active_user
from app.modules.carrito import service
from app.modules.carrito.schemas import (
    AgregarItemRequest,
    ModificarCantidadRequest,
    AplicarDescuentoRequest,
    CarritoResponse,
)

router = APIRouter(prefix="/carrito", tags=["Carrito"])


@router.get("", response_model=CarritoResponse)
async def obtener_carrito(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    carrito = await service.get_or_create_carrito(db, current_user.id)
    return service.calcular_totales(carrito)


@router.post("/items", response_model=CarritoResponse, status_code=status.HTTP_201_CREATED)
async def agregar_item(
    data: AgregarItemRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        carrito = await service.agregar_item(db, current_user.id, data.producto_id, data.cantidad)
        return service.calcular_totales(carrito)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/items/{producto_id}", response_model=CarritoResponse)
async def modificar_cantidad(
    producto_id: uuid.UUID,
    data: ModificarCantidadRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        carrito = await service.modificar_cantidad(
            db, current_user.id, producto_id, data.cantidad
        )
        return service.calcular_totales(carrito)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/items/{producto_id}", response_model=CarritoResponse)
async def eliminar_item(
    producto_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        carrito = await service.eliminar_item(db, current_user.id, producto_id)
        return service.calcular_totales(carrito)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def vaciar_carrito(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await service.vaciar_carrito(db, current_user.id)


@router.post("/descuento", response_model=CarritoResponse)
async def aplicar_descuento(
    data: AplicarDescuentoRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        carrito = await service.aplicar_descuento(db, current_user.id, data.codigo)
        return service.calcular_totales(carrito)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/descuento", response_model=CarritoResponse)
async def remover_descuento(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    carrito = await service.remover_descuento(db, current_user.id)
    return service.calcular_totales(carrito)
