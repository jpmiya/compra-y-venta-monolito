import pytest
from httpx import AsyncClient

from app.modules.productos.models import Producto


@pytest.mark.asyncio
async def test_carrito_vacio_inicial(client: AsyncClient):
    response = await client.get("/carrito")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["subtotal"] == 0.0
    assert data["total"] == 0.0


@pytest.mark.asyncio
async def test_agregar_item(client: AsyncClient, producto_test: Producto):
    response = await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 2},
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["cantidad"] == 2
    assert data["subtotal"] == pytest.approx(2000.0)


@pytest.mark.asyncio
async def test_agregar_item_acumula_cantidad(
    client: AsyncClient, producto_test: Producto
):
    await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 1},
    )
    response = await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 3},
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["cantidad"] == 4


@pytest.mark.asyncio
async def test_agregar_item_sin_stock_rechazado(
    client: AsyncClient, producto_test: Producto
):
    response = await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 999},
    )
    assert response.status_code == 400
    assert "stock" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_agregar_item_producto_inexistente(client: AsyncClient):
    response = await client.post(
        "/carrito/items",
        json={
            "producto_id": "00000000-0000-0000-0000-000000000000",
            "cantidad": 1,
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_agregar_item_cantidad_cero_rechazada(
    client: AsyncClient, producto_test: Producto
):
    response = await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 0},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_modificar_cantidad_item(
    client: AsyncClient, producto_test: Producto
):
    await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 1},
    )
    response = await client.put(
        f"/carrito/items/{producto_test.id}",
        json={"cantidad": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["cantidad"] == 5


@pytest.mark.asyncio
async def test_modificar_item_inexistente(
    client: AsyncClient, producto_test: Producto
):
    response = await client.put(
        f"/carrito/items/{producto_test.id}",
        json={"cantidad": 2},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_eliminar_item(
    client: AsyncClient, producto_test: Producto
):
    await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 1},
    )
    response = await client.delete(f"/carrito/items/{producto_test.id}")
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_eliminar_item_inexistente(
    client: AsyncClient, producto_test: Producto
):
    response = await client.delete(f"/carrito/items/{producto_test.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_vaciar_carrito(
    client: AsyncClient, producto_test: Producto
):
    await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 2},
    )
    response = await client.delete("/carrito")
    assert response.status_code == 204

    carrito = await client.get("/carrito")
    assert carrito.json()["items"] == []


@pytest.mark.asyncio
async def test_aplicar_codigo_descuento(
    client: AsyncClient, producto_test: Producto
):
    await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 1},
    )
    response = await client.post(
        "/carrito/descuento", json={"codigo": "PROMO20"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["codigo_descuento"] == "PROMO20"
    assert data["descuento"] == pytest.approx(200.0)
    assert data["total"] == pytest.approx(800.0)


@pytest.mark.asyncio
async def test_aplicar_codigo_descuento_invalido(client: AsyncClient):
    response = await client.post(
        "/carrito/descuento", json={"codigo": "NO_EXISTE"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_remover_descuento(
    client: AsyncClient, producto_test: Producto
):
    await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 1},
    )
    await client.post("/carrito/descuento", json={"codigo": "PROMO10"})

    response = await client.delete("/carrito/descuento")
    assert response.status_code == 200
    data = response.json()
    assert data["codigo_descuento"] is None
    assert data["descuento"] == 0.0
