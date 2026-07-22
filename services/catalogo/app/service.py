import math
import uuid
from typing import Optional, List, Tuple

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.persistence.models import Producto, Categoria, Resena, MensajeProcesado
from app.adapters.rest.schemas import ProductoCreate, ProductoUpdate, ResenaCreate, ItemStockCmd
from app.core.http_client import IdentidadClient

CAMPOS_ORDEN_VALIDOS = {"nombre", "precio", "calificacion_promedio", "fecha_creacion"}

STOCK_DISPONIBLE = Producto.stock - Producto.stock_reservado


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
    # Solo productos con stock DISPONIBLE (físico - reservado por sagas en curso)
    query = select(Producto).where(Producto.activo == True, STOCK_DISPONIBLE > 0)

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


# --- Composición síncrona en lectura (dirección de punto de venta vive en Identidad) ---

async def resolver_direcciones(
    identidad: IdentidadClient, productos: List[Producto]
) -> dict:
    """Resuelve en batch las direcciones de punto de venta de un listado.

    Devuelve {direccion_id(str): direccion(dict)}. Si Identidad no responde,
    degrada devolviendo {} (los productos salen con direccion_punto_venta=None
    en lugar de romper la búsqueda).
    """
    ids_unicos = list({p.direccion_punto_venta_id for p in productos})
    try:
        direcciones = await identidad.get_direcciones(ids_unicos)
    except Exception:
        return {}
    return {d["id"]: d for d in direcciones}


async def validar_direccion_vendedor(
    identidad: IdentidadClient, direccion_id: uuid.UUID, vendedor: dict
) -> dict:
    """La dirección del punto de venta debe existir, estar activa y pertenecer al vendedor.

    Antes era un SELECT sobre la tabla `direcciones`; ahora es una llamada
    síncrona a Identidad (dueño del dato).
    """
    direccion = await identidad.get_direccion(direccion_id)
    if not direccion or not direccion.get("activa"):
        raise ValueError("Dirección no encontrada o inactiva")
    if direccion.get("persona_id") != vendedor.get("persona_id"):
        raise ValueError("La dirección no pertenece al vendedor")
    return direccion


async def crear_producto(
    db: AsyncSession, identidad: IdentidadClient, data: ProductoCreate, vendedor: dict
) -> Producto:
    await validar_direccion_vendedor(identidad, data.direccion_punto_venta_id, vendedor)
    producto = Producto(
        nombre=data.nombre,
        descripcion=data.descripcion,
        precio=data.precio,
        categoria_id=data.categoria_id,
        stock=data.stock,
        sku=data.sku,
        imagenes=data.imagenes,
        vendedor_id=uuid.UUID(vendedor["id"]),
        direccion_punto_venta_id=data.direccion_punto_venta_id,
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
    db: AsyncSession, producto: Producto, usuario_id: uuid.UUID, data: ResenaCreate
) -> Resena:
    resena = Resena(
        producto_id=producto.id,
        usuario_id=usuario_id,
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


# --- Handlers de la saga de checkout (idempotentes por message_id) ---
#
# ReservarStock: aparta stock (stock_reservado += cantidad) validando disponible.
# DescontarStock: confirma la reserva tras el pivote (stock -= y stock_reservado -=).
# LiberarStock: compensación de ReservarStock (stock_reservado -=).
#
# Idempotencia: solo se registra el message_id cuando el comando MUTÓ estado.
# Un comando rechazado (sin efectos) puede reintentarse y se reevalúa.

async def _resultado_previo(
    db: AsyncSession, message_id: uuid.UUID, handler: str
) -> Optional[MensajeProcesado]:
    result = await db.execute(
        select(MensajeProcesado).where(
            MensajeProcesado.message_id == message_id,
            MensajeProcesado.handler == handler,
        )
    )
    return result.scalar_one_or_none()


async def _productos_por_id(
    db: AsyncSession, items: List[ItemStockCmd]
) -> dict:
    ids = [item.producto_id for item in items]
    result = await db.execute(select(Producto).where(Producto.id.in_(ids)))
    return {p.id: p for p in result.scalars().all()}


async def reservar_stock(
    db: AsyncSession, message_id: uuid.UUID, items: List[ItemStockCmd]
) -> Tuple[bool, Optional[str]]:
    previo = await _resultado_previo(db, message_id, "reservar_stock")
    if previo:
        return previo.ok, previo.error

    productos = await _productos_por_id(db, items)

    # Validación todo-o-nada antes de mutar
    for item in items:
        producto = productos.get(item.producto_id)
        if not producto or not producto.activo:
            return False, f"Producto {item.producto_id} no encontrado o inactivo"
        if producto.stock_disponible < item.cantidad:
            return False, f"Stock insuficiente para '{producto.nombre}'"

    for item in items:
        productos[item.producto_id].stock_reservado += item.cantidad

    db.add(MensajeProcesado(message_id=message_id, handler="reservar_stock", ok=True))
    await db.commit()
    return True, None


async def descontar_stock(
    db: AsyncSession, message_id: uuid.UUID, items: List[ItemStockCmd]
) -> Tuple[bool, Optional[str]]:
    """Confirma la reserva tras el pivote: baja stock físico y libera la reserva."""
    previo = await _resultado_previo(db, message_id, "descontar_stock")
    if previo:
        return previo.ok, previo.error

    productos = await _productos_por_id(db, items)

    for item in items:
        if item.producto_id not in productos:
            return False, f"Producto {item.producto_id} no encontrado"

    for item in items:
        producto = productos[item.producto_id]
        producto.stock -= item.cantidad
        producto.stock_reservado = max(0, producto.stock_reservado - item.cantidad)

    db.add(MensajeProcesado(message_id=message_id, handler="descontar_stock", ok=True))
    await db.commit()
    return True, None


async def liberar_stock(
    db: AsyncSession, message_id: uuid.UUID, items: List[ItemStockCmd]
) -> Tuple[bool, Optional[str]]:
    """Compensación de ReservarStock. Tolerante: libera lo que exista, nunca falla."""
    previo = await _resultado_previo(db, message_id, "liberar_stock")
    if previo:
        return previo.ok, previo.error

    productos = await _productos_por_id(db, items)

    for item in items:
        producto = productos.get(item.producto_id)
        if producto:
            producto.stock_reservado = max(0, producto.stock_reservado - item.cantidad)

    db.add(MensajeProcesado(message_id=message_id, handler="liberar_stock", ok=True))
    await db.commit()
    return True, None
