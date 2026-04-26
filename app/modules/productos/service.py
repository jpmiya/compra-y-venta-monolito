import math
import uuid
from typing import Optional, List

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import Usuario
from app.modules.productos.models import Producto, Categoria, Resena
from app.modules.productos.schemas import ProductoCreate, ProductoUpdate, ResenaCreate

CAMPOS_ORDEN_VALIDOS = {"nombre", "precio", "calificacion_promedio", "fecha_creacion"}


async def listar_productos(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    busqueda: Optional[str] = None,
    categoria_id: Optional[uuid.UUID] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    orden: str = "fecha_creacion",
    ascendente: bool = False,
) -> dict:
    query = select(Producto).where(Producto.activo == True)

    if busqueda:
        query = query.where(
            or_(
                Producto.nombre.ilike(f"%{busqueda}%"),
                Producto.descripcion.ilike(f"%{busqueda}%"),
            )
        )
    if categoria_id:
        query = query.where(Producto.categoria_id == categoria_id)
    if precio_min is not None:
        query = query.where(Producto.precio >= precio_min)
    if precio_max is not None:
        query = query.where(Producto.precio <= precio_max)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    col = getattr(Producto, orden if orden in CAMPOS_ORDEN_VALIDOS else "fecha_creacion")
    query = query.order_by(col.asc() if ascendente else col.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total > 0 else 0,
    }


async def get_producto_by_id(db: AsyncSession, producto_id: uuid.UUID) -> Optional[Producto]:
    result = await db.execute(select(Producto).where(Producto.id == producto_id))
    return result.scalar_one_or_none()


async def get_producto_by_sku(db: AsyncSession, sku: str) -> Optional[Producto]:
    result = await db.execute(select(Producto).where(Producto.sku == sku))
    return result.scalar_one_or_none()


async def crear_producto(db: AsyncSession, data: ProductoCreate, vendedor: Usuario) -> Producto:
    producto = Producto(
        nombre=data.nombre,
        descripcion=data.descripcion,
        precio=data.precio,
        categoria_id=data.categoria_id,
        stock=data.stock,
        sku=data.sku,
        imagenes=data.imagenes,
        vendedor_id=vendedor.id,
    )
    db.add(producto)
    await db.commit()
    await db.refresh(producto)
    return producto


async def actualizar_producto(
    db: AsyncSession, producto: Producto, data: ProductoUpdate
) -> Producto:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(producto, field, value)
    await db.commit()
    await db.refresh(producto)
    return producto


async def eliminar_producto(db: AsyncSession, producto: Producto) -> None:
    producto.activo = False
    await db.commit()


async def listar_categorias(db: AsyncSession) -> List[Categoria]:
    result = await db.execute(select(Categoria))
    return result.scalars().all()


async def agregar_resena(
    db: AsyncSession, producto: Producto, usuario: Usuario, data: ResenaCreate
) -> Resena:
    resena = Resena(
        producto_id=producto.id,
        usuario_id=usuario.id,
        calificacion=data.calificacion,
        comentario=data.comentario,
    )
    db.add(resena)
    await db.flush()

    promedio_result = await db.execute(
        select(func.avg(Resena.calificacion)).where(Resena.producto_id == producto.id)
    )
    promedio = promedio_result.scalar_one() or 0.0
    producto.calificacion_promedio = round(float(promedio), 2)

    await db.commit()
    await db.refresh(resena)
    return resena
