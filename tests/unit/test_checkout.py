import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.productos.models import Producto


@pytest.mark.asyncio
async def test_checkout_carrito_vacio_rechazado(client: AsyncClient):
    response = await client.post(
        "/carrito/checkout", json={"direccion_entrega": "Calle Falsa 123"}
    )
    assert response.status_code == 400
    assert "vacío" in response.json()["detail"]


@pytest.mark.asyncio
async def test_checkout_sin_saldo_rechazado(
    client: AsyncClient, producto_test: Producto
):
    await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 1},
    )

    response = await client.post(
        "/carrito/checkout", json={"direccion_entrega": "Calle Falsa 123"}
    )
    assert response.status_code == 400
    assert "saldo" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_checkout_exitoso(
    client: AsyncClient, db: AsyncSession, producto_test: Producto
):
    await client.post("/billetera/cargar", json={"monto": 50000.0})
    await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 2},
    )

    response = await client.post(
        "/carrito/checkout", json={"direccion_entrega": "Av. Siempre Viva 742"}
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["delivery_orders"]) == 1
    assert data["total_cobrado"] == pytest.approx(2000.0)
    assert data["delivery_orders"][0]["estado"] == "pendiente"


@pytest.mark.asyncio
async def test_checkout_descuenta_saldo(
    client: AsyncClient, producto_test: Producto
):
    await client.post("/billetera/cargar", json={"monto": 50000.0})
    await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 1},
    )
    await client.post(
        "/carrito/checkout", json={"direccion_entrega": "Calle Test 1"}
    )

    billetera = await client.get("/billetera")
    assert billetera.json()["saldo"] == pytest.approx(49000.0)


@pytest.mark.asyncio
async def test_checkout_vacia_carrito(
    client: AsyncClient, producto_test: Producto
):
    await client.post("/billetera/cargar", json={"monto": 50000.0})
    await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 1},
    )
    await client.post(
        "/carrito/checkout", json={"direccion_entrega": "Calle Test 2"}
    )

    carrito = await client.get("/carrito")
    assert carrito.json()["items"] == []


@pytest.mark.asyncio
async def test_checkout_descuenta_stock(
    client: AsyncClient, db: AsyncSession, producto_test: Producto
):
    stock_inicial = producto_test.stock
    await client.post("/billetera/cargar", json={"monto": 50000.0})
    await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 3},
    )
    await client.post(
        "/carrito/checkout", json={"direccion_entrega": "Calle Test 3"}
    )

    await db.refresh(producto_test)
    assert producto_test.stock == stock_inicial - 3


@pytest.mark.asyncio
async def test_checkout_genera_transaccion_en_historial(
    client: AsyncClient, producto_test: Producto
):
    await client.post("/billetera/cargar", json={"monto": 50000.0})
    await client.post(
        "/carrito/items",
        json={"producto_id": str(producto_test.id), "cantidad": 1},
    )
    await client.post(
        "/carrito/checkout", json={"direccion_entrega": "Calle Test 4"}
    )

    historial = await client.get("/billetera/historial")
    tipos = [t["tipo"] for t in historial.json()["transacciones"]]
    assert "compra" in tipos
