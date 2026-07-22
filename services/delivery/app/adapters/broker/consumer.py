"""Adaptador de entrada asincrónico: consume CrearDeliveriesCmd desde RabbitMQ.

Diseño (plan §9): el orquestador (Carrito) publica el comando en la cola
`delivery.crear_deliveries` con un `reply_queue` propio por saga (canales de
respuesta múltiples, no una cola general única). Delivery procesa idempotente
y publica DeliveriesCreado en ese canal de respuesta.

`procesar_crear_deliveries` es transporte-agnóstico (recibe el publicador como
puerto) para poder testearlo sin broker; `RabbitMQConsumer` es el adaptador real.
"""
import asyncio
import json
import logging
from typing import Awaitable, Callable

import aio_pika

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app import service
from app.adapters.rest.schemas import CrearDeliveriesCmd, DeliveriesCreado

logger = logging.getLogger(__name__)

# Puerto de salida: publicar la respuesta en el canal indicado
PublicarRespuesta = Callable[[str, DeliveriesCreado], Awaitable[None]]


async def procesar_crear_deliveries(
    payload: bytes,
    session_factory,
    publicar_respuesta: PublicarRespuesta,
) -> DeliveriesCreado:
    """Procesa un CrearDeliveriesCmd y publica la confirmación en su reply_queue."""
    cmd = CrearDeliveriesCmd.model_validate_json(payload)

    async with session_factory() as db:
        ok, delivery_ids = await service.crear_deliveries_idempotente(
            db, cmd.message_id, cmd.items
        )

    respuesta = DeliveriesCreado(saga_id=cmd.saga_id, delivery_ids=delivery_ids, ok=ok)
    await publicar_respuesta(cmd.reply_queue, respuesta)
    return respuesta


class RabbitMQConsumer:
    def __init__(self, rabbitmq_url: str = None):
        self.rabbitmq_url = rabbitmq_url or settings.RABBITMQ_URL
        self._connection = None
        self._channel = None

    async def _publicar_respuesta(self, reply_queue: str, respuesta: DeliveriesCreado) -> None:
        # Canal de respuesta propio por saga: se declara (idempotente en AMQP)
        # y se publica por el default exchange con routing_key = nombre de la cola.
        await self._channel.declare_queue(reply_queue, durable=True)
        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=respuesta.model_dump_json().encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=reply_queue,
        )

    async def _on_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        # requeue en fallo: el comando es idempotente, la reentrega es segura
        async with message.process(requeue=True):
            await procesar_crear_deliveries(
                message.body, AsyncSessionLocal, self._publicar_respuesta
            )

    async def run(self) -> None:
        """Loop del consumer con reconexión (robust connection de aio-pika)."""
        while True:
            try:
                self._connection = await aio_pika.connect_robust(self.rabbitmq_url)
                async with self._connection:
                    self._channel = await self._connection.channel()
                    await self._channel.set_qos(prefetch_count=10)
                    queue = await self._channel.declare_queue(
                        settings.COLA_CREAR_DELIVERIES, durable=True
                    )
                    logger.info("Consumer escuchando cola %s", settings.COLA_CREAR_DELIVERIES)
                    await queue.consume(self._on_message)
                    await asyncio.Future()  # correr hasta cancelación
            except asyncio.CancelledError:
                logger.info("Consumer cancelado")
                raise
            except Exception:
                logger.exception("Consumer caído; reintento en 5s")
                await asyncio.sleep(5)
