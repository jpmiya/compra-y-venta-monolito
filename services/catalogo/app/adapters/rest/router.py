import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_usuario
from app.core.http_client import IdentidadClient, get_identidad_client
from app import service
from app.adapters.rest.schemas import (
    ProductoCreate,
    ProductoUpdate,
    ProductoResponse,
    ProductoListResponse,
    DireccionPuntoVentaResponse,
    CategoriaResponse,
    ResenaCreate,
)

router = APIRouter(tags=["Catálogo"])


def _componer(producto, direcciones: dict) -> ProductoResponse:
    """Arma la respuesta componiendo la dirección resuelta desde Identidad."""
    respuesta = ProductoResponse.model_validate(producto)
    direccion = direcciones.get(str(producto.direccion_punto_venta_id))
    if direccion:
        respuesta.direccion_punto_venta = DireccionPuntoVentaResponse.model_validate(direccion)
    return respuesta


async def _listar(
    db: AsyncSession,
    identidad: IdentidadClient,
    page: int,
    page_size: int,
    busqueda: Optional[str],
    categoria_id: Optional[uuid.UUID],
    precio_min: Optional[float],
    precio_max: Optional[float],
    orden: str,
    ascendente: bool,
) -> ProductoListResponse:
    resultado = await service.listar_productos(
        db, page, page_size, busqueda, categoria_id, precio_min, precio_max, orden, ascendente
    )
    direcciones = await service.resolver_direcciones(identidad, resultado["items"])
    return ProductoListResponse(
        items=[_componer(p, direcciones) for p in resultado["items"]],
        total=resultado["total"],
        page=resultado["page"],
        page_size=resultado["page_size"],
        pages=resultado["pages"],
    )


# --- Productos ---

@router.get("/productos", response_model=ProductoListResponse)
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
    identidad: IdentidadClient = Depends(get_identidad_client),
):
    return await _listar(
        db, identidad, page, page_size, busqueda, categoria_id, precio_min, precio_max, orden, ascendente
    )


@router.get("/productos/categorias", response_model=List[CategoriaResponse])
async def listar_categorias(db: AsyncSession = Depends(get_db)):
    return await service.listar_categorias(db)


@router.get("/productos/{producto_id}", response_model=ProductoResponse)
async def obtener_producto(
    producto_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identidad: IdentidadClient = Depends(get_identidad_client),
):
    producto = await service.get_producto_by_id(db, producto_id)
    if not producto or not producto.activo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    direcciones = await service.resolver_direcciones(identidad, [producto])
    return _componer(producto, direcciones)


@router.post("/productos", response_model=ProductoResponse, status_code=status.HTTP_201_CREATED)
async def crear_producto(
    data: ProductoCreate,
    current_user: dict = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db),
    identidad: IdentidadClient = Depends(get_identidad_client),
):
    if await service.get_producto_by_sku(db, data.sku):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU ya registrado")
    try:
        producto = await service.crear_producto(db, identidad, data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    direcciones = await service.resolver_direcciones(identidad, [producto])
    return _componer(producto, direcciones)


@router.put("/productos/{producto_id}", response_model=ProductoResponse)
async def actualizar_producto(
    producto_id: uuid.UUID,
    data: ProductoUpdate,
    current_user: dict = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db),
    identidad: IdentidadClient = Depends(get_identidad_client),
):
    producto = await service.get_producto_by_id(db, producto_id)
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    producto = await service.actualizar_producto(db, producto, data)
    direcciones = await service.resolver_direcciones(identidad, [producto])
    return _componer(producto, direcciones)


@router.delete("/productos/{producto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_producto(
    producto_id: uuid.UUID,
    current_user: dict = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db),
):
    producto = await service.get_producto_by_id(db, producto_id)
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    await service.eliminar_producto(db, producto)


@router.post("/productos/{producto_id}/resena", status_code=status.HTTP_201_CREATED)
async def agregar_resena(
    producto_id: uuid.UUID,
    data: ResenaCreate,
    current_user: dict = Depends(get_current_usuario),
    db: AsyncSession = Depends(get_db),
):
    producto = await service.get_producto_by_id(db, producto_id)
    if not producto or not producto.activo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return await service.agregar_resena(
        db, producto, uuid.UUID(current_user["id"]), data
    )


# --- Búsqueda (capacidad de consulta sobre el catálogo) ---

@router.get("/busqueda", response_model=ProductoListResponse)
async def buscar(
    q: Optional[str] = Query(None, description="Búsqueda por texto libre"),
    categoria_id: Optional[uuid.UUID] = Query(None),
    precio_min: Optional[float] = Query(None, ge=0),
    precio_max: Optional[float] = Query(None, ge=0),
    orden: str = Query(
        "fecha_creacion",
        pattern="^(nombre|precio|calificacion_promedio|fecha_creacion)$",
    ),
    ascendente: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    identidad: IdentidadClient = Depends(get_identidad_client),
):
    return await _listar(
        db, identidad, page, page_size, q, categoria_id, precio_min, precio_max, orden, ascendente
    )
