"""Tests del handler CrearDeliveries (asincrónico post-pivote, idempotente).

Se testea `procesar_crear_deliveries` (transporte-agnóstico) con un publicador
fake en lugar del canal RabbitMQ real: mismo código que corre el consumer,
sin necesitar broker en los tests.
"""
import json
import uuid

import pytest
from httpx import AsyncClient

from app.adapters.broker.consumer import procesar_crear_deliveries
from tests.conftest import COMPRADOR_ID, PRODUCTO_ID, DIRECCION_PV_ID


class PublicadorFake:
    """Puerto de respuesta fake: acumula (reply_queue, respuesta) publicados."""

    def __init__(self):
        self.publicados = []

    async def __call__(self, reply_queue, respuesta):
        self.publicados.append((reply_queue, respuesta))


def _cmd(message_id=None, saga_id=None, items=2):
    saga = saga_id or uuid.uuid4()
    return json.dumps({
        "message_id": str(message_id or uuid.uuid4()),
        "saga_id": str(saga),
        "reply_queue": f"carrito.respuesta.{saga}",
        "items": [
            {
                "producto_id": str(PRODUCTO_ID),
                "comprador_id": str(COMPRADOR_ID),
                "cantidad": i + 1,
                "precio_unitario": 500.0,
                "direccion_entrega": "Av. Test 999",
                "direccion_punto_venta_id": str(DIRECCION_PV_ID),
            }
            for i in range(items)
        ],
    }).encode()


@pytest.mark.asyncio
async def test_crear_deliveries_uno_por_item(client: AsyncClient, session_factory):
    """Igual que el checkout del monolito: un DeliveryOrder por ítem, en estado pendiente."""
    publicador = PublicadorFake()
    respuesta = await procesar_crear_deliveries(_cmd(items=3), session_factory, publicador)

    assert respuesta.ok is True
    assert len(respuesta.delivery_ids) == 3

    pendientes = await client.get("/deliveries")
    assert len(pendientes.json()) == 3
    assert all(d["estado"] == "pendiente" for d in pendientes.json())


@pytest.mark.asyncio
async def test_respuesta_va_al_reply_queue_de_la_saga(session_factory):
    """Canal de respuesta múltiple: la confirmación se publica en la cola propia del saga_id."""
    saga_id = uuid.uuid4()
    publicador = PublicadorFake()

    await procesar_crear_deliveries(_cmd(saga_id=saga_id), session_factory, publicador)

    assert len(publicador.publicados) == 1
    reply_queue, respuesta = publicador.publicados[0]
    assert reply_queue == f"carrito.respuesta.{saga_id}"
    assert respuesta.saga_id == saga_id
    assert respuesta.ok is True


@pytest.mark.asyncio
async def test_crear_deliveries_idempotente(client: AsyncClient, session_factory):
    """Reentrega del mismo message_id (retry del log del orquestador):
    no crea duplicados y devuelve los MISMOS delivery_ids."""
    message_id = uuid.uuid4()
    publicador = PublicadorFake()

    r1 = await procesar_crear_deliveries(
        _cmd(message_id=message_id, items=2), session_factory, publicador
    )
    r2 = await procesar_crear_deliveries(
        _cmd(message_id=message_id, items=2), session_factory, publicador
    )

    assert r1.delivery_ids == r2.delivery_ids
    # La respuesta se re-publica igual (el orquestador pudo no haberla recibido)
    assert len(publicador.publicados) == 2

    pendientes = await client.get("/deliveries")
    assert len(pendientes.json()) == 2  # no 4


@pytest.mark.asyncio
async def test_mensajes_distintos_crean_deliveries_distintos(client: AsyncClient, session_factory):
    publicador = PublicadorFake()
    r1 = await procesar_crear_deliveries(_cmd(items=1), session_factory, publicador)
    r2 = await procesar_crear_deliveries(_cmd(items=1), session_factory, publicador)

    assert set(r1.delivery_ids).isdisjoint(set(r2.delivery_ids))
    pendientes = await client.get("/deliveries")
    assert len(pendientes.json()) == 2
