"""Tests de la CheckoutSaga: camino feliz, compensación y log de deliverys con retry.

Cubre los dos escenarios exigidos por el plan §10:
- Camino de fallo con compensación real: saldo insuficiente → LiberarStock → 402.
- Retry de delivery desde el log (broker caído → reenvío con el mismo message_id).
"""
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.adapters.persistence.models import SagaCheckout, DeliveryLog
from app import saga as saga_module
from tests.conftest import (
    FIXED_USER_ID,
    PRODUCTO_ID,
    PRODUCTO_2_ID,
    DIRECCION_PV_ID,
    PublicadorFake,
)


async def _checkout(client: AsyncClient):
    return await client.post(
        "/carrito/checkout", json={"direccion_entrega": "Av. Test 999"}
    )


# --- Camino feliz ---

@pytest.mark.asyncio
async def test_checkout_camino_feliz(client: AsyncClient, db, fake_catalogo, fake_billetera):
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 2})
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_2_ID), "cantidad": 1})

    response = await _checkout(client)
    assert response.status_code == 201
    data = response.json()
    assert data["estado"] == "completada"
    assert data["total_cobrado"] == 2500.0
    assert data["saldo_restante"] == 97500.0
    assert data["items_comprados"] == 2

    # Orquestación: reservó → debitó → confirmó (descontó); sin compensación
    assert len(fake_catalogo.reservas) == 1
    assert len(fake_billetera.debitos) == 1
    assert fake_billetera.debitos[0][1] == 2500.0
    assert len(fake_catalogo.descuentos) == 1
    assert fake_catalogo.liberaciones == []

    # El carrito quedó vacío
    assert (await client.get("/carrito")).json()["items"] == []

    # Saga persistida como completada + log de delivery escrito (outbox)
    saga = (await db.execute(select(SagaCheckout))).scalar_one()
    assert saga.estado == "completada"
    log = (await db.execute(select(DeliveryLog))).scalar_one()
    assert log.saga_id == saga.id
    payload = json.loads(log.payload)
    assert len(payload["items"]) == 2
    assert payload["reply_queue"] == f"carrito.respuesta.{saga.id}"
    assert all(
        i["direccion_punto_venta_id"] == str(DIRECCION_PV_ID) for i in payload["items"]
    )


@pytest.mark.asyncio
async def test_checkout_aplica_descuento(client: AsyncClient, fake_billetera):
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 1})
    await client.post("/carrito/descuento", json={"codigo": "PROMO20"})

    response = await _checkout(client)
    assert response.status_code == 201
    assert response.json()["total_cobrado"] == 800.0
    assert fake_billetera.debitos[0][1] == 800.0


@pytest.mark.asyncio
async def test_checkout_carrito_vacio(client: AsyncClient):
    response = await _checkout(client)
    assert response.status_code == 400
    assert "vacío" in response.json()["detail"].lower()


# --- Fallo pre-pivote: ReservarStock rechazado ---

@pytest.mark.asyncio
async def test_checkout_stock_insuficiente(client: AsyncClient, db, fake_catalogo, fake_billetera):
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 5})
    # Otro comprador agotó el stock entre el agregar y el checkout
    fake_catalogo.productos[str(PRODUCTO_ID)]["stock_disponible"] = 1

    response = await _checkout(client)
    assert response.status_code == 409
    assert "insuficiente" in response.json()["detail"].lower()

    # No llegó al pivote, no hay nada que compensar
    assert fake_billetera.debitos == []
    assert fake_catalogo.liberaciones == []

    saga = (await db.execute(select(SagaCheckout))).scalar_one()
    assert saga.estado == "fallida"
    assert saga.error is not None

    # El carrito NO se vació: el usuario puede reintentar
    assert len((await client.get("/carrito")).json()["items"]) == 1


# --- Fallo en el pivote: compensación real (plan §10) ---

@pytest.mark.asyncio
async def test_checkout_saldo_insuficiente_compensa_stock(
    client: AsyncClient, db, fake_catalogo, fake_billetera
):
    """Pivote falla → LiberarStock devuelve la reserva → 402 → saga compensada."""
    fake_billetera.saldo = 100.0  # no alcanza
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 2})
    disponible_antes = fake_catalogo.productos[str(PRODUCTO_ID)]["stock_disponible"]

    response = await _checkout(client)
    assert response.status_code == 402
    assert "insuficiente" in response.json()["detail"].lower()

    # Se reservó y luego se compensó: el stock disponible volvió al valor original
    assert len(fake_catalogo.reservas) == 1
    assert len(fake_catalogo.liberaciones) == 1
    assert fake_catalogo.productos[str(PRODUCTO_ID)]["stock_disponible"] == disponible_antes
    # DescontarStock nunca corrió
    assert fake_catalogo.descuentos == []

    saga = (await db.execute(select(SagaCheckout))).scalar_one()
    assert saga.estado == "compensada"

    # Sin delivery log (la saga no llegó a completarse) y el carrito sigue lleno
    assert (await db.execute(select(DeliveryLog))).scalar_one_or_none() is None
    assert len((await client.get("/carrito")).json()["items"]) == 1


# --- Log de deliverys: outbox + retry (plan §10) ---

@pytest.mark.asyncio
async def test_publicar_delivery_marca_enviado(client: AsyncClient, db):
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 1})
    saga_id = uuid.UUID((await _checkout(client)).json()["saga_id"])

    publicador = PublicadorFake()
    ok = await saga_module.publicar_delivery_pendiente(db, publicador, saga_id)
    assert ok is True
    assert len(publicador.publicados) == 1
    _, reply_queue = publicador.publicados[0]
    assert reply_queue == f"carrito.respuesta.{saga_id}"

    log = (await db.execute(select(DeliveryLog))).scalar_one()
    assert log.estado == "enviado"
    assert log.intentos == 1


@pytest.mark.asyncio
async def test_retry_desde_el_log_con_broker_caido(client: AsyncClient, db):
    """Broker caído en el checkout → log queda pendiente_envio → el worker de
    retry lo reenvía con el MISMO message_id cuando el broker vuelve."""
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 1})
    saga_id = uuid.UUID((await _checkout(client)).json()["saga_id"])

    # Primer intento: broker caído
    caido = PublicadorFake(fallar=True)
    ok = await saga_module.publicar_delivery_pendiente(db, caido, saga_id)
    assert ok is False
    log = (await db.execute(select(DeliveryLog))).scalar_one()
    assert log.estado == "pendiente_envio"
    assert log.intentos == 1
    message_id_original = log.message_id

    # El broker vuelve: el worker reenvía desde el log
    vivo = PublicadorFake()
    reenviados = await saga_module.reintentar_deliveries_pendientes(db, vivo)
    assert reenviados == 1
    payload, _ = vivo.publicados[0]
    # Mismo message_id → Delivery (idempotente) no duplica aunque hubiera recibido el primero
    assert json.loads(payload)["message_id"] == str(message_id_original)

    await db.refresh(log)
    assert log.estado == "enviado"
    assert log.intentos == 2


@pytest.mark.asyncio
async def test_confirmacion_marca_log_confirmado(client: AsyncClient, db):
    """DeliveriesCreado recibido en el canal de la saga → log confirmado → sin más retries."""
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 1})
    saga_id = uuid.UUID((await _checkout(client)).json()["saga_id"])

    publicador = PublicadorFake()
    await saga_module.publicar_delivery_pendiente(db, publicador, saga_id)
    ok = await saga_module.confirmar_delivery(db, saga_id)
    assert ok is True

    log = (await db.execute(select(DeliveryLog))).scalar_one()
    assert log.estado == "confirmado"
    assert log.fecha_confirmacion is not None

    # El worker de retry ya no lo levanta
    reenviados = await saga_module.reintentar_deliveries_pendientes(db, publicador)
    assert reenviados == 0
    assert len(publicador.publicados) == 1  # solo el envío original


@pytest.mark.asyncio
async def test_message_ids_deterministicos_por_saga():
    """Un reintento del orquestador reusa el mismo message_id por paso."""
    saga_id = uuid.uuid4()
    assert saga_module._message_id(saga_id, "reservar_stock") == saga_module._message_id(
        saga_id, "reservar_stock"
    )
    assert saga_module._message_id(saga_id, "reservar_stock") != saga_module._message_id(
        saga_id, "debitar_saldo"
    )
    assert saga_module._message_id(saga_id, "reservar_stock") != saga_module._message_id(
        uuid.uuid4(), "reservar_stock"
    )


@pytest.mark.asyncio
async def test_estado_saga_consultable(client: AsyncClient, db):
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 1})
    saga_id = (await _checkout(client)).json()["saga_id"]

    response = await client.get(f"/carrito/checkout/{saga_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "completada"
    assert data["delivery_estado"] == "pendiente_envio"  # broker apagado en tests
    assert data["usuario_id"] == str(FIXED_USER_ID)
