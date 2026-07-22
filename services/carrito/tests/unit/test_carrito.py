"""Tests del carrito — el producto se valida contra Catálogo (fake), no en BD local."""
import pytest
from httpx import AsyncClient

from tests.conftest import PRODUCTO_ID, PRODUCTO_2_ID


@pytest.mark.asyncio
async def test_carrito_vacio_inicial(client: AsyncClient):
    response = await client.get("/carrito")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0.0


@pytest.mark.asyncio
async def test_agregar_item(client: AsyncClient):
    response = await client.post(
        "/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 2}
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["cantidad"] == 2
    assert data["items"][0]["precio_unitario"] == 1000.0
    assert data["total"] == 2000.0


@pytest.mark.asyncio
async def test_agregar_item_acumula_cantidad(client: AsyncClient):
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 2})
    response = await client.post(
        "/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 3}
    )
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["cantidad"] == 5


@pytest.mark.asyncio
async def test_agregar_item_producto_inexistente(client: AsyncClient):
    response = await client.post(
        "/carrito/items",
        json={"producto_id": "00000000-0000-0000-0000-000000000099", "cantidad": 1},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_agregar_item_stock_insuficiente(client: AsyncClient):
    response = await client.post(
        "/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 99}
    )
    assert response.status_code == 400
    assert "insuficiente" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_modificar_cantidad(client: AsyncClient):
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 2})
    response = await client.put(
        f"/carrito/items/{PRODUCTO_ID}", json={"cantidad": 4}
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["cantidad"] == 4


@pytest.mark.asyncio
async def test_eliminar_item(client: AsyncClient):
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 2})
    response = await client.delete(f"/carrito/items/{PRODUCTO_ID}")
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_vaciar_carrito(client: AsyncClient):
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 2})
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_2_ID), "cantidad": 1})
    response = await client.delete("/carrito")
    assert response.status_code == 204
    assert (await client.get("/carrito")).json()["items"] == []


@pytest.mark.asyncio
async def test_aplicar_descuento(client: AsyncClient):
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 1})
    response = await client.post("/carrito/descuento", json={"codigo": "PROMO20"})
    assert response.status_code == 200
    data = response.json()
    assert data["descuento"] == 200.0
    assert data["total"] == 800.0


@pytest.mark.asyncio
async def test_descuento_invalido(client: AsyncClient):
    await client.post("/carrito/items", json={"producto_id": str(PRODUCTO_ID), "cantidad": 1})
    response = await client.post("/carrito/descuento", json={"codigo": "NOEXISTE"})
    assert response.status_code == 400
