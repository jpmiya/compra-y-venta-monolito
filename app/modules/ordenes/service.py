import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.admin.models import Usuario
from app.modules.carrito.models import Carrito, CarritoItem
from app.modules.ordenes.models import Orden, OrdenItem
from app.modules.ordenes.schemas import (
    ActualizarEstadoRequest,
    CrearOrdenRequest,
    TASA_IMPUESTO,
    TRANSICIONES_VALIDAS,
)
from app.modules.productos.models import Producto


async def _generar_numero_orden(db: AsyncSession) -> str:
    result = await db.execute(select(func.count(Orden.id)))
    count = result.scalar_one() + 1
    year = datetime.now().year
    return f"ORD-{year}-{count:04d}"


async def get_orden_by_id(db: AsyncSession, orden_id: uuid.UUID) -> Optional[Orden]:
    result = await db.execute(
        select(Orden).options(selectinload(Orden.items)).where(Orden.id == orden_id)
    )
    return result.scalar_one_or_none()


async def listar_ordenes(db: AsyncSession, usuario_id: uuid.UUID) -> List[Orden]:
    result = await db.execute(
        select(Orden)
        .options(selectinload(Orden.items))
        .where(Orden.usuario_id == usuario_id)
        .order_by(Orden.fecha_creacion.desc())
    )
    return result.scalars().all()


async def crear_orden(
    db: AsyncSession, usuario_id: uuid.UUID, data: CrearOrdenRequest
) -> Orden:
    carrito_result = await db.execute(
        select(Carrito)
        .options(selectinload(Carrito.items))
        .where(Carrito.usuario_id == usuario_id)
    )
    carrito = carrito_result.scalar_one_or_none()
    if not carrito or not carrito.items:
        raise ValueError("El carrito está vacío")

    orden_pendiente = await db.execute(
        select(Orden).where(Orden.usuario_id == usuario_id, Orden.estado == "pendiente")
    )
    if orden_pendiente.scalar_one_or_none():
        raise ValueError("Ya tienes una orden pendiente")

    subtotal = 0.0
    orden_items_data = []

    for item in carrito.items:
        prod_result = await db.execute(select(Producto).where(Producto.id == item.producto_id))
        producto = prod_result.scalar_one_or_none()
        if not producto or not producto.activo:
            raise ValueError(f"Producto {item.producto_id} no disponible")
        if producto.stock < item.cantidad:
            raise ValueError(f"Stock insuficiente para '{producto.nombre}'")

        orden_items_data.append(
            {
                "producto": producto,
                "cantidad": item.cantidad,
                "precio_unitario": item.precio_unitario,
                "nombre_producto": producto.nombre,
            }
        )
        subtotal += item.cantidad * item.precio_unitario

    descuento = carrito.descuento or 0.0
    base_imponible = max(0.0, subtotal - descuento)
    impuesto = round(base_imponible * TASA_IMPUESTO, 2)
    total = round(base_imponible + impuesto, 2)

    orden = Orden(
        numero_orden=await _generar_numero_orden(db),
        usuario_id=usuario_id,
        subtotal=round(subtotal, 2),
        impuesto=impuesto,
        descuento=descuento,
        total=total,
        direccion_entrega=data.direccion_entrega,
        telefono_contacto=data.telefono_contacto,
    )
    db.add(orden)
    await db.flush()

    for d in orden_items_data:
        db.add(
            OrdenItem(
                orden_id=orden.id,
                producto_id=d["producto"].id,
                nombre_producto=d["nombre_producto"],
                cantidad=d["cantidad"],
                precio_unitario=d["precio_unitario"],
            )
        )
        d["producto"].stock -= d["cantidad"]

    for item in carrito.items:
        await db.delete(item)
    carrito.codigo_descuento = None
    carrito.descuento = 0.0

    await db.commit()
    return await get_orden_by_id(db, orden.id)


async def actualizar_estado(
    db: AsyncSession, orden: Orden, data: ActualizarEstadoRequest
) -> Orden:
    transiciones = TRANSICIONES_VALIDAS.get(orden.estado, set())
    if data.estado not in transiciones:
        raise ValueError(
            f"Transición inválida: '{orden.estado}' → '{data.estado}'. "
            f"Permitidas: {transiciones or 'ninguna'}"
        )
    orden.estado = data.estado
    if data.numero_seguimiento:
        orden.numero_seguimiento = data.numero_seguimiento
    orden.fecha_actualizacion = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(orden)
    return orden


async def cancelar_orden(
    db: AsyncSession, orden: Orden, usuario_id: uuid.UUID
) -> Orden:
    if str(orden.usuario_id) != str(usuario_id):
        raise ValueError("No autorizado para cancelar esta orden")
    if orden.estado != "pendiente":
        raise ValueError("Solo se pueden cancelar órdenes en estado 'pendiente'")

    for item in orden.items:
        prod_result = await db.execute(select(Producto).where(Producto.id == item.producto_id))
        producto = prod_result.scalar_one_or_none()
        if producto:
            producto.stock += item.cantidad

    orden.estado = "cancelada"
    orden.fecha_actualizacion = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(orden)
    return orden
