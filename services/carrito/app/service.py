import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.persistence.models import Carrito, CarritoItem
from app.core.http_client import CatalogoClient

logger = logging.getLogger(__name__)

MAX_ITEMS = 100

# Códigos de descuento hardcodeados; en producción vendrían de BD
CODIGOS_DESCUENTO: dict[str, float] = {
    "PROMO20": 0.20,
    "PROMO10": 0.10,
}


async def _cargar_carrito(db: AsyncSession, usuario_id: uuid.UUID) -> Carrito:
    # populate_existing fuerza el refresh de la colección items aunque el Carrito
    # ya esté en el identity map (misma técnica que el monolito).
    result = await db.execute(
        select(Carrito)
        .options(selectinload(Carrito.items))
        .where(Carrito.usuario_id == usuario_id)
        .execution_options(populate_existing=True)
    )
    carrito = result.scalar_one_or_none()
    if not carrito:
        carrito = Carrito(usuario_id=usuario_id)
        db.add(carrito)
        await db.commit()
        result = await db.execute(
            select(Carrito)
            .options(selectinload(Carrito.items))
            .where(Carrito.id == carrito.id)
            .execution_options(populate_existing=True)
        )
        carrito = result.scalar_one()
    return carrito


async def get_or_create_carrito(db: AsyncSession, usuario_id: uuid.UUID) -> Carrito:
    return await _cargar_carrito(db, usuario_id)


async def agregar_item(
    db: AsyncSession,
    catalogo: CatalogoClient,
    usuario_id: uuid.UUID,
    producto_id: uuid.UUID,
    cantidad: int,
) -> Carrito:
    """El producto ya no vive en la BD local: se valida contra Catálogo.

    El chequeo de stock acá es informativo (mejor UX al agregar); la validación
    definitiva es ReservarStock dentro de la saga de checkout.
    """
    carrito = await _cargar_carrito(db, usuario_id)

    producto = await catalogo.get_producto(producto_id)
    if not producto or not producto.get("activo"):
        raise ValueError("Producto no encontrado o inactivo")

    item_result = await db.execute(
        select(CarritoItem).where(
            CarritoItem.carrito_id == carrito.id,
            CarritoItem.producto_id == producto_id,
        )
    )
    item = item_result.scalar_one_or_none()

    if item:
        nueva_cantidad = item.cantidad + cantidad
        if producto["stock_disponible"] < nueva_cantidad:
            raise ValueError("Stock insuficiente para la cantidad solicitada")
        item.cantidad = nueva_cantidad
    else:
        if len(carrito.items) >= MAX_ITEMS:
            raise ValueError("El carrito no puede tener más de 100 items")
        if producto["stock_disponible"] < cantidad:
            raise ValueError("Stock insuficiente")
        item = CarritoItem(
            carrito_id=carrito.id,
            producto_id=producto_id,
            cantidad=cantidad,
            precio_unitario=producto["precio"],
        )
        db.add(item)

    await db.commit()
    return await _cargar_carrito(db, usuario_id)


async def modificar_cantidad(
    db: AsyncSession,
    catalogo: CatalogoClient,
    usuario_id: uuid.UUID,
    producto_id: uuid.UUID,
    cantidad: int,
) -> Carrito:
    carrito = await _cargar_carrito(db, usuario_id)

    item_result = await db.execute(
        select(CarritoItem).where(
            CarritoItem.carrito_id == carrito.id,
            CarritoItem.producto_id == producto_id,
        )
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise ValueError("Item no encontrado en el carrito")

    producto = await catalogo.get_producto(producto_id)
    if not producto or producto["stock_disponible"] < cantidad:
        raise ValueError("Stock insuficiente")

    item.cantidad = cantidad
    await db.commit()
    return await _cargar_carrito(db, usuario_id)


async def eliminar_item(
    db: AsyncSession, usuario_id: uuid.UUID, producto_id: uuid.UUID
) -> Carrito:
    carrito = await _cargar_carrito(db, usuario_id)

    item_result = await db.execute(
        select(CarritoItem).where(
            CarritoItem.carrito_id == carrito.id,
            CarritoItem.producto_id == producto_id,
        )
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise ValueError("Item no encontrado en el carrito")

    await db.delete(item)
    await db.commit()
    return await _cargar_carrito(db, usuario_id)


async def vaciar_carrito(db: AsyncSession, usuario_id: uuid.UUID) -> None:
    carrito = await _cargar_carrito(db, usuario_id)
    for item in carrito.items:
        await db.delete(item)
    carrito.codigo_descuento = None
    carrito.descuento = 0.0
    await db.commit()


async def aplicar_descuento(db: AsyncSession, usuario_id: uuid.UUID, codigo: str) -> Carrito:
    carrito = await _cargar_carrito(db, usuario_id)
    porcentaje = CODIGOS_DESCUENTO.get(codigo.upper())
    if not porcentaje:
        raise ValueError("Código de descuento inválido o vencido")

    subtotal = sum(i.cantidad * i.precio_unitario for i in carrito.items)
    carrito.codigo_descuento = codigo.upper()
    carrito.descuento = round(subtotal * porcentaje, 2)
    await db.commit()
    return await _cargar_carrito(db, usuario_id)


async def remover_descuento(db: AsyncSession, usuario_id: uuid.UUID) -> Carrito:
    carrito = await _cargar_carrito(db, usuario_id)
    carrito.codigo_descuento = None
    carrito.descuento = 0.0
    await db.commit()
    return await _cargar_carrito(db, usuario_id)


def calcular_totales(carrito: Carrito) -> dict:
    subtotal = sum(i.cantidad * i.precio_unitario for i in carrito.items)
    total = max(0.0, subtotal - carrito.descuento)
    return {
        "id": carrito.id,
        "usuario_id": carrito.usuario_id,
        "items": [
            {
                "producto_id": i.producto_id,
                "cantidad": i.cantidad,
                "precio_unitario": i.precio_unitario,
                "subtotal": round(i.cantidad * i.precio_unitario, 2),
            }
            for i in carrito.items
        ],
        "subtotal": round(subtotal, 2),
        "descuento": carrito.descuento,
        "total": round(total, 2),
        "codigo_descuento": carrito.codigo_descuento,
        "fecha_creacion": carrito.fecha_creacion,
    }
