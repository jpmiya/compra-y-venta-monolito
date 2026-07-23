"""CheckoutSaga — el orquestador de la compra distribuida (plan §5.2).

Reemplaza el checkout atómico del monolito (un commit ACID) por una saga por
orquestación con pasos sincrónicos y un tramo asincrónico final:

    1. ReservarStock   (Catálogo, sync)   — compensable
    2. DebitarSaldo    (Billetera, sync)  — PIVOTE go/no-go
       └─ si falla → LiberarStock (compensación) → saga compensada
    3. DescontarStock  (Catálogo, sync)   — confirma la reserva, post-pivote
    4. Vaciar carrito + escribir DeliveryLog (outbox) — transacción local
    5. CrearDeliveries (Delivery, ASYNC vía RabbitMQ) — con retry desde el log

Los message_id son determinísticos por (saga, paso): un reintento del
orquestador reusa el mismo id y los participantes idempotentes no duplican.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.adapters.persistence.models import SagaCheckout, DeliveryLog
from app.adapters.broker.publisher import reply_queue_de
from app.core.http_client import CatalogoClient, BilleteraClient
from app.service import _cargar_carrito
from app.adapters.rest.schemas import CrearDeliveriesCmd, DeliveryItemCmd

logger = logging.getLogger(__name__)

# Sagas con un listener de confirmación activo — evita apilar consumers
# duplicados en el mismo canal de respuesta cuando el worker de retry
# reintenta antes de que el listener anterior haya vencido su timeout.
_escuchando_confirmacion: set[uuid.UUID] = set()


async def escuchar_confirmacion(publicador, saga_id: uuid.UUID) -> None:
    """Espera DeliveriesCreado en el canal de la saga y marca el log confirmado.

    Se llama tanto tras el primer intento de publicación (checkout) como tras
    cada reenvío del worker de retry: republicar sin volver a escuchar deja
    la respuesta de Delivery varada en la cola sin consumer (bug real
    detectado en el e2e: el worker reenviaba el comando pero nadie quedaba
    esperando la confirmación, así que la saga nunca salía de "enviado").
    """
    if saga_id in _escuchando_confirmacion:
        return
    _escuchando_confirmacion.add(saga_id)
    try:
        respuesta = await publicador.esperar_confirmacion(reply_queue_de(saga_id))
        if respuesta and respuesta.get("ok"):
            async with AsyncSessionLocal() as db:
                await confirmar_delivery(db, saga_id)
    finally:
        _escuchando_confirmacion.discard(saga_id)


class CarritoVacioError(Exception):
    pass


class StockError(Exception):
    pass


class SaldoInsuficienteError(Exception):
    pass


def _message_id(saga_id: uuid.UUID, paso: str) -> uuid.UUID:
    """Determinístico por (saga, paso): el retry reusa el mismo message_id."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"saga:{saga_id}:{paso}")


async def ejecutar_checkout(
    db: AsyncSession,
    catalogo: CatalogoClient,
    billetera: BilleteraClient,
    usuario_id: uuid.UUID,
    direccion_entrega: str,
) -> dict:
    """Corre la saga hasta dejar el DeliveryLog escrito (outbox).

    La publicación a RabbitMQ NO ocurre acá: queda a cargo del caller
    (`publicar_delivery_pendiente`) y del worker de retry — así el checkout
    responde aunque el broker esté caído.
    """
    carrito = await _cargar_carrito(db, usuario_id)
    if not carrito.items:
        raise CarritoVacioError("El carrito está vacío")

    # Datos de productos (direccion_punto_venta_id para los deliveries) — Catálogo es el dueño
    productos = {}
    for item in carrito.items:
        producto = await catalogo.get_producto(item.producto_id)
        if not producto or not producto.get("activo"):
            raise StockError(f"Producto {item.producto_id} no encontrado o inactivo")
        productos[item.producto_id] = producto

    subtotal = sum(i.cantidad * i.precio_unitario for i in carrito.items)
    total = round(max(0.0, subtotal - carrito.descuento), 2)

    # Estado de saga persistido ANTES de tocar otros servicios
    saga = SagaCheckout(
        usuario_id=usuario_id, direccion_entrega=direccion_entrega, total=total
    )
    db.add(saga)
    await db.commit()
    await db.refresh(saga)

    items_cmd = [
        {"producto_id": str(i.producto_id), "cantidad": i.cantidad} for i in carrito.items
    ]

    # --- Paso 1: ReservarStock (compensable) ---
    respuesta = await catalogo.reservar_stock(
        _message_id(saga.id, "reservar_stock"), saga.id, items_cmd
    )
    if not respuesta["ok"]:
        saga.estado = "fallida"
        saga.error = respuesta["error"]
        await db.commit()
        logger.info("SAGA %s fallida en ReservarStock: %s", saga.id, saga.error)
        raise StockError(respuesta["error"])
    saga.estado = "stock_reservado"
    await db.commit()

    # --- Paso 2: DebitarSaldo (PIVOTE) ---
    respuesta = await billetera.debitar_saldo(
        _message_id(saga.id, "debitar_saldo"),
        usuario_id,
        total,
        f"Compra: {len(carrito.items)} item(s) — {total} {settings.CARRITO_MONEDA}",
    )
    if not respuesta["ok"]:
        # Compensación: devolver la reserva de stock
        await catalogo.liberar_stock(
            _message_id(saga.id, "liberar_stock"), saga.id, items_cmd
        )
        saga.estado = "compensada"
        saga.error = respuesta["error"]
        await db.commit()
        logger.info("SAGA %s compensada (pivote falló): %s", saga.id, saga.error)
        raise SaldoInsuficienteError(respuesta["error"])
    saldo_restante = respuesta["saldo_resultante"]
    saga.estado = "debitada"
    await db.commit()

    # --- Paso 3: DescontarStock (confirma la reserva; post-pivote, no aborta) ---
    respuesta = await catalogo.descontar_stock(
        _message_id(saga.id, "descontar_stock"), saga.id, items_cmd
    )
    if not respuesta["ok"]:
        # Post-pivote no hay vuelta atrás: se registra y sigue (retry manual/worker)
        saga.error = f"DescontarStock falló: {respuesta['error']}"
        logger.error("SAGA %s: %s", saga.id, saga.error)
    saga.estado = "stock_descontado"
    await db.commit()

    # --- Paso 4: transacción local — vaciar carrito + outbox del delivery ---
    cmd = CrearDeliveriesCmd(
        message_id=_message_id(saga.id, "crear_deliveries"),
        saga_id=saga.id,
        reply_queue=reply_queue_de(saga.id),
        items=[
            DeliveryItemCmd(
                producto_id=item.producto_id,
                comprador_id=usuario_id,
                cantidad=item.cantidad,
                precio_unitario=item.precio_unitario,
                direccion_entrega=direccion_entrega,
                direccion_punto_venta_id=uuid.UUID(
                    productos[item.producto_id]["direccion_punto_venta_id"]
                ),
            )
            for item in carrito.items
        ],
    )
    items_comprados = len(carrito.items)
    for item in carrito.items:
        await db.delete(item)
    carrito.codigo_descuento = None
    carrito.descuento = 0.0
    db.add(
        DeliveryLog(
            saga_id=saga.id,
            message_id=cmd.message_id,
            payload=cmd.model_dump_json(),
        )
    )
    saga.estado = "completada"
    await db.commit()

    logger.info(
        "SAGA %s completada usuario=%s items=%d total=%.2f",
        saga.id, usuario_id, items_comprados, total,
    )
    return {
        "saga_id": saga.id,
        "estado": saga.estado,
        "total_cobrado": total,
        "saldo_restante": saldo_restante,
        "moneda": settings.CARRITO_MONEDA,
        "items_comprados": items_comprados,
    }


# --- Outbox del delivery: publicación + retry + confirmación ---

async def publicar_delivery_pendiente(
    db: AsyncSession, publicador, saga_id: uuid.UUID
) -> bool:
    """Primer intento de envío tras el checkout. Si el broker falla, el log queda
    en pendiente_envio y el worker de retry lo levanta después."""
    result = await db.execute(select(DeliveryLog).where(DeliveryLog.saga_id == saga_id))
    log = result.scalar_one_or_none()
    if not log or log.estado == "confirmado":
        return False
    try:
        await publicador.publicar(log.payload, reply_queue_de(log.saga_id))
    except Exception:
        logger.exception("No se pudo publicar CrearDeliveries de saga %s (queda en el log)", saga_id)
        log.intentos += 1
        await db.commit()
        return False
    log.estado = "enviado"
    log.intentos += 1
    await db.commit()
    return True


async def reintentar_deliveries_pendientes(db: AsyncSession, publicador) -> int:
    """Worker de retry: re-publica todo log no confirmado. Los participantes son
    idempotentes por message_id, así que reenviar es siempre seguro."""
    result = await db.execute(
        select(DeliveryLog).where(DeliveryLog.estado.in_(["pendiente_envio", "enviado"]))
    )
    reenviados = 0
    for log in result.scalars().all():
        try:
            await publicador.publicar(log.payload, reply_queue_de(log.saga_id))
            log.estado = "enviado"
            reenviados += 1
            asyncio.create_task(escuchar_confirmacion(publicador, log.saga_id))
        except Exception:
            logger.exception("Retry de saga %s falló; se reintenta en el próximo ciclo", log.saga_id)
        log.intentos += 1
    await db.commit()
    return reenviados


async def confirmar_delivery(db: AsyncSession, saga_id: uuid.UUID) -> bool:
    """Marca el log como confirmado cuando llega DeliveriesCreado por el canal de la saga."""
    result = await db.execute(select(DeliveryLog).where(DeliveryLog.saga_id == saga_id))
    log = result.scalar_one_or_none()
    if not log:
        return False
    log.estado = "confirmado"
    log.fecha_confirmacion = datetime.now(timezone.utc)
    await db.commit()
    logger.info("Delivery de saga %s confirmado", saga_id)
    return True


async def get_saga(db: AsyncSession, saga_id: uuid.UUID) -> Optional[SagaCheckout]:
    result = await db.execute(select(SagaCheckout).where(SagaCheckout.id == saga_id))
    return result.scalar_one_or_none()
