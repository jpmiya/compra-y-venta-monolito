"""Tests de los handlers de stock de la saga de checkout.

Ciclo: ReservarStock (pre-pivote, compensable) → DescontarStock (confirma tras
DebitarSaldo ok) | LiberarStock (compensación si el pivote falla).
Todos idempotentes por message_id.
"""
import uuid

import pytest
from httpx import AsyncClient

from app.adapters.persistence.models import Producto


def _cmd(producto_id, cantidad, message_id=None):
    return {
        "message_id": str(message_id or uuid.uuid4()),
        "saga_id": str(uuid.uuid4()),
        "items": [{"producto_id": str(producto_id), "cantidad": cantidad}],
    }


async def _stock(client: AsyncClient, producto_id) -> dict:
    response = await client.get(f"/interno/productos/{producto_id}")
    return response.json()


@pytest.mark.asyncio
async def test_reservar_stock_ok(internal_client: AsyncClient, producto_test: Producto):
    response = await internal_client.post(
        "/interno/stock/reservar", json=_cmd(producto_test.id, 3)
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True

    producto = await _stock(internal_client, producto_test.id)
    assert producto["stock"] == 10          # el físico no cambia al reservar
    assert producto["stock_reservado"] == 3
    assert producto["stock_disponible"] == 7


@pytest.mark.asyncio
async def test_reservar_stock_insuficiente(internal_client: AsyncClient, producto_test: Producto):
    response = await internal_client.post(
        "/interno/stock/reservar", json=_cmd(producto_test.id, 99)
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert "insuficiente" in data["error"].lower()

    producto = await _stock(internal_client, producto_test.id)
    assert producto["stock_reservado"] == 0  # sin efectos


@pytest.mark.asyncio
async def test_reservar_stock_todo_o_nada(internal_client: AsyncClient, producto_test: Producto):
    """Si un ítem del comando no tiene stock, no se reserva NINGUNO."""
    cmd = {
        "message_id": str(uuid.uuid4()),
        "saga_id": str(uuid.uuid4()),
        "items": [
            {"producto_id": str(producto_test.id), "cantidad": 2},
            {"producto_id": str(uuid.uuid4()), "cantidad": 1},  # inexistente
        ],
    }
    response = await internal_client.post("/interno/stock/reservar", json=cmd)
    assert response.json()["ok"] is False

    producto = await _stock(internal_client, producto_test.id)
    assert producto["stock_reservado"] == 0


@pytest.mark.asyncio
async def test_reservar_stock_idempotente(internal_client: AsyncClient, producto_test: Producto):
    """El mismo message_id no debe reservar dos veces."""
    message_id = uuid.uuid4()
    cmd = _cmd(producto_test.id, 4, message_id)

    r1 = await internal_client.post("/interno/stock/reservar", json=cmd)
    assert r1.json()["ok"] is True

    r2 = await internal_client.post("/interno/stock/reservar", json=cmd)
    assert r2.json()["ok"] is True

    producto = await _stock(internal_client, producto_test.id)
    assert producto["stock_reservado"] == 4  # una sola reserva, no 8


@pytest.mark.asyncio
async def test_liberar_stock_compensa_reserva(internal_client: AsyncClient, producto_test: Producto):
    """Pivote falló → LiberarStock devuelve la reserva y el producto vuelve a estar disponible."""
    await internal_client.post("/interno/stock/reservar", json=_cmd(producto_test.id, 10))
    producto = await _stock(internal_client, producto_test.id)
    assert producto["stock_disponible"] == 0

    response = await internal_client.post(
        "/interno/stock/liberar", json=_cmd(producto_test.id, 10)
    )
    assert response.json()["ok"] is True

    producto = await _stock(internal_client, producto_test.id)
    assert producto["stock"] == 10
    assert producto["stock_reservado"] == 0
    assert producto["stock_disponible"] == 10


@pytest.mark.asyncio
async def test_liberar_stock_idempotente(internal_client: AsyncClient, producto_test: Producto):
    await internal_client.post("/interno/stock/reservar", json=_cmd(producto_test.id, 6))

    message_id = uuid.uuid4()
    cmd = _cmd(producto_test.id, 3, message_id)
    await internal_client.post("/interno/stock/liberar", json=cmd)
    await internal_client.post("/interno/stock/liberar", json=cmd)

    producto = await _stock(internal_client, producto_test.id)
    assert producto["stock_reservado"] == 3  # liberó 3 una sola vez, no 6


@pytest.mark.asyncio
async def test_descontar_stock_confirma_reserva(internal_client: AsyncClient, producto_test: Producto):
    """Pivote ok → DescontarStock baja el stock físico y libera la reserva."""
    await internal_client.post("/interno/stock/reservar", json=_cmd(producto_test.id, 4))

    response = await internal_client.post(
        "/interno/stock/descontar", json=_cmd(producto_test.id, 4)
    )
    assert response.json()["ok"] is True

    producto = await _stock(internal_client, producto_test.id)
    assert producto["stock"] == 6
    assert producto["stock_reservado"] == 0
    assert producto["stock_disponible"] == 6


@pytest.mark.asyncio
async def test_descontar_stock_idempotente(internal_client: AsyncClient, producto_test: Producto):
    await internal_client.post("/interno/stock/reservar", json=_cmd(producto_test.id, 4))

    message_id = uuid.uuid4()
    cmd = _cmd(producto_test.id, 4, message_id)
    await internal_client.post("/interno/stock/descontar", json=cmd)
    await internal_client.post("/interno/stock/descontar", json=cmd)

    producto = await _stock(internal_client, producto_test.id)
    assert producto["stock"] == 6  # descontó una sola vez, no dos


@pytest.mark.asyncio
async def test_ciclo_reserva_visible_en_busqueda(
    client: AsyncClient, internal_client: AsyncClient, producto_test: Producto
):
    """Integración de la reserva con la búsqueda pública: reservar todo el stock
    saca el producto del catálogo; liberar lo devuelve."""
    r = await client.get("/busqueda", params={"q": "Notebook"})
    assert r.json()["total"] == 1

    await internal_client.post("/interno/stock/reservar", json=_cmd(producto_test.id, 10))
    r = await client.get("/busqueda", params={"q": "Notebook"})
    assert r.json()["total"] == 0

    await internal_client.post("/interno/stock/liberar", json=_cmd(producto_test.id, 10))
    r = await client.get("/busqueda", params={"q": "Notebook"})
    assert r.json()["total"] == 1
