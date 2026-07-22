"""Adaptador de salida asincrónico: publica CrearDeliveriesCmd en RabbitMQ.

El puerto es `PublicadorDeliveries` (una callable async que recibe el payload
serializado y el reply_queue). El adaptador real publica en la cola de Delivery
y deja un consumer escuchando el canal de respuesta propio de la saga para
marcar el log como confirmado cuando llega DeliveriesCreado.
"""
import asyncio
import json
import logging
import uuid

import aio_pika

from app.core.config import settings

logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    def __init__(self, rabbitmq_url: str = None):
        self.rabbitmq_url = rabbitmq_url or settings.RABBITMQ_URL

    async def publicar(self, payload: str, reply_queue: str) -> None:
        """Publica el comando en la cola de Delivery. Lanza excepción si el broker no está
        (el caller deja el log en pendiente_envio y el worker de retry lo reintenta)."""
        connection = await aio_pika.connect_robust(self.rabbitmq_url, timeout=5)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(settings.COLA_CREAR_DELIVERIES, durable=True)
            # El canal de respuesta se declara acá para que exista aunque Delivery
            # responda antes de que nos suscribamos.
            await channel.declare_queue(reply_queue, durable=True)
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=payload.encode(),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=settings.COLA_CREAR_DELIVERIES,
            )
        logger.info("CrearDeliveriesCmd publicado (reply=%s)", reply_queue)

    async def esperar_confirmacion(
        self, reply_queue: str, timeout: float = 30.0
    ) -> dict | None:
        """Espera DeliveriesCreado en el canal de respuesta de la saga.
        Devuelve el payload dict o None si venció el timeout (el retry se encarga)."""
        try:
            connection = await aio_pika.connect_robust(self.rabbitmq_url, timeout=5)
            async with connection:
                channel = await connection.channel()
                queue = await channel.declare_queue(reply_queue, durable=True)
                async with queue.iterator(timeout=timeout) as it:
                    async for message in it:
                        async with message.process():
                            respuesta = json.loads(message.body)
                            logger.info("DeliveriesCreado recibido en %s", reply_queue)
                            return respuesta
        except (asyncio.TimeoutError, TimeoutError):
            logger.warning("Timeout esperando confirmación en %s", reply_queue)
            return None
        except Exception:
            logger.exception("Error esperando confirmación en %s", reply_queue)
            return None


def get_publicador() -> RabbitMQPublisher:
    return RabbitMQPublisher()


def reply_queue_de(saga_id: uuid.UUID) -> str:
    """Canal de respuesta propio por saga (canales múltiples, plan §9)."""
    return f"{settings.REPLY_QUEUE_PREFIX}.{saga_id}"
