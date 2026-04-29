import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.modules.carrito.models import Carrito, CarritoItem
from app.modules.delivery.models import DeliveryOrder
from app.modules.productos.models import Producto

MAX_ITEMS = 100

# Códigos de descuento hardcodeados; en producción vendrían de BD
CODIGOS_DESCUENTO: dict[str, float] = {
    "PROMO20": 0.20,
    "PROMO10": 0.10,
}


async def _cargar_carrito(db: AsyncSession, usuario_id: uuid.UUID) -> Carrito:
    result = await db.execute(
        select(Carrito)
        .options(selectinload(Carrito.items))
        .where(Carrito.usuario_id == usuario_id)
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
        )
        carrito = result.scalar_one()
    return carrito


async def get_or_create_carrito(db: AsyncSession, usuario_id: uuid.UUID) -> Carrito:
    return await _cargar_carrito(db, usuario_id)


async def agregar_item(
    db: AsyncSession, usuario_id: uuid.UUID, producto_id: uuid.UUID, cantidad: int
) -> Carrito:
    carrito = await _cargar_carrito(db, usuario_id)

    prod_result = await db.execute(
        select(Producto).where(Producto.id == producto_id, Producto.activo == True)
    )
    producto = prod_result.scalar_one_or_none()
    if not producto:
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
        if producto.stock < nueva_cantidad:
            raise ValueError("Stock insuficiente para la cantidad solicitada")
        item.cantidad = nueva_cantidad
    else:
        if len(carrito.items) >= MAX_ITEMS:
            raise ValueError("El carrito no puede tener más de 100 items")
        if producto.stock < cantidad:
            raise ValueError("Stock insuficiente")
        item = CarritoItem(
            carrito_id=carrito.id,
            producto_id=producto_id,
            cantidad=cantidad,
            precio_unitario=producto.precio,
        )
        db.add(item)

    await db.commit()
    return await _cargar_carrito(db, usuario_id)


async def modificar_cantidad(
    db: AsyncSession, usuario_id: uuid.UUID, producto_id: uuid.UUID, cantidad: int
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

    prod_result = await db.execute(select(Producto).where(Producto.id == producto_id))
    producto = prod_result.scalar_one_or_none()
    if not producto or producto.stock < cantidad:
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


async def checkout(
    db: AsyncSession, usuario_id: uuid.UUID, direccion_entrega: str
) -> dict:
    from app.modules.billetera.service import get_or_create_billetera, descontar_saldo

    carrito = await _cargar_carrito(db, usuario_id)
    if not carrito.items:
        raise ValueError("El carrito está vacío")

    # Validar stock de cada item y cargar productos
    productos = {}
    for item in carrito.items:
        result = await db.execute(
            select(Producto).where(Producto.id == item.producto_id, Producto.activo == True)
        )
        producto = result.scalar_one_or_none()
        if not producto:
            raise ValueError(f"Producto {item.producto_id} no encontrado o inactivo")
        if producto.stock < item.cantidad:
            raise ValueError(f"Stock insuficiente para '{producto.nombre}'")
        productos[item.producto_id] = producto

    # Calcular total con descuento
    subtotal = sum(i.cantidad * i.precio_unitario for i in carrito.items)
    total = round(max(0.0, subtotal - carrito.descuento), 2)

    # Verificar saldo en billetera
    billetera = await get_or_create_billetera(db, usuario_id)
    if billetera.saldo < total:
        raise ValueError("Saldo insuficiente en la billetera")

    # Crear DeliveryOrder y descontar stock por cada item
    delivery_orders = []
    for item in carrito.items:
        producto = productos[item.producto_id]
        order = DeliveryOrder(
            comprador_id=usuario_id,
            producto_id=item.producto_id,
            cantidad=item.cantidad,
            precio_unitario=item.precio_unitario,
            direccion_entrega=direccion_entrega,
            direccion_punto_venta_id=producto.direccion_punto_venta_id,
        )
        db.add(order)
        delivery_orders.append(order)
        producto.stock -= item.cantidad

    # Descontar billetera (sin commit propio)
    await descontar_saldo(
        db,
        billetera,
        total,
        f"Compra: {len(carrito.items)} item(s) — {total} {billetera.moneda}",
    )

    # Vaciar carrito
    for item in carrito.items:
        await db.delete(item)
    carrito.codigo_descuento = None
    carrito.descuento = 0.0

    # Commit único — todo o nada
    await db.commit()

    logger.info(
        "CHECKOUT usuario=%s items=%d total=%.2f %s",
        usuario_id, len(carrito.items), total, billetera.moneda,
    )

    return {
        "delivery_orders": delivery_orders,
        "total_cobrado": total,
        "moneda": billetera.moneda,
    }


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
