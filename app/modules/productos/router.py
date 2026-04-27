import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_active_user
from app.modules.productos import service
from app.modules.productos.schemas import (
    ProductoCreate,
    ProductoUpdate,
    ProductoResponse,
    ProductoListResponse,
    CategoriaResponse,
    ResenaCreate,
)

router = APIRouter(prefix="/productos", tags=["Productos"])


@router.get("", response_model=ProductoListResponse)
async def listar_productos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    busqueda: Optional[str] = Query(None),
    categoria_id: Optional[uuid.UUID] = Query(None),
    precio_min: Optional[float] = Query(None, ge=0),
    precio_max: Optional[float] = Query(None, ge=0),
    orden: str = Query(
        "fecha_creacion",
        pattern="^(nombre|precio|calificacion_promedio|fecha_creacion)$",
    ),
    ascendente: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    return await service.listar_productos(
        db, page, page_size, busqueda, categoria_id, precio_min, precio_max, orden, ascendente
    )


@router.get("/categorias", response_model=list[CategoriaResponse])
async def listar_categorias(db: AsyncSession = Depends(get_db)):
    return await service.listar_categorias(db)


@router.get("/{producto_id}", response_model=ProductoResponse)
async def obtener_producto(producto_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    producto = await service.get_producto_by_id(db, producto_id)
    if not producto or not producto.activo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return producto


@router.post("", response_model=ProductoResponse, status_code=status.HTTP_201_CREATED)
async def crear_producto(
    data: ProductoCreate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if await service.get_producto_by_sku(db, data.sku):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU ya registrado")
    try:
        return await service.crear_producto(db, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{producto_id}", response_model=ProductoResponse)
async def actualizar_producto(
    producto_id: uuid.UUID,
    data: ProductoUpdate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    producto = await service.get_producto_by_id(db, producto_id)
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return await service.actualizar_producto(db, producto, data)


@router.delete("/{producto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_producto(
    producto_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    producto = await service.get_producto_by_id(db, producto_id)
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    await service.eliminar_producto(db, producto)


@router.post("/{producto_id}/resena", status_code=status.HTTP_201_CREATED)
async def agregar_resena(
    producto_id: uuid.UUID,
    data: ResenaCreate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    producto = await service.get_producto_by_id(db, producto_id)
    if not producto or not producto.activo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return await service.agregar_resena(db, producto, current_user, data)
