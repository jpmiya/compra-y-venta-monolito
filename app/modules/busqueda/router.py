import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.modules.productos import service as productos_service
from app.modules.productos.schemas import ProductoListResponse

router = APIRouter(prefix="/busqueda", tags=["Búsqueda"])


@router.get("", response_model=ProductoListResponse)
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
):
    return await productos_service.listar_productos(
        db, page, page_size, q, categoria_id, precio_min, precio_max, orden, ascendente
    )
