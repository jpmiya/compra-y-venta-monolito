import pytest
from httpx import AsyncClient

from app.modules.productos.models import Producto


async def _hacer_checkout(client: AsyncClient, producto: Producto, cantidad: int = 1):
    """Helper: carga saldo, agrega item y hace checkout. Retorna el primer delivery_order."""
    await client.post("/billetera/cargar", json={"monto": 50000.0})
    await client.post(
        "/carrito/items",
        json={"producto_id": str(producto.id), "cantidad": cantidad},
    )
    resp = await client.post(
        "/carrito/checkout", json={"direccion_entrega": "Av. Test 999"}
    )
    return resp.json()["delivery_orders"][0]


@pytest.mark.asyncio
async def test_listar_pendientes_incluye_delivery_creado(
    client: AsyncClient, producto_test: Producto
):
    await _hacer_checkout(client, producto_test)

    response = await client.get("/deliveries")
    assert response.status_code == 200
    estados = [d["estado"] for d in response.json()]
    assert "pendiente" in estados


@pytest.mark.asyncio
async def test_obtener_detalle_delivery(
    client: AsyncClient, producto_test: Producto
):
    order = await _hacer_checkout(client, producto_test)

    response = await client.get(f"/deliveries/{order['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == order["id"]
    assert data["estado"] == "pendiente"


@pytest.mark.asyncio
async def test_tomar_delivery_cambia_estado(
    client: AsyncClient, producto_test: Producto
):
    order = await _hacer_checkout(client, producto_test)

    response = await client.post(f"/deliveries/{order['id']}/tomar")
    assert response.status_code == 200
    assert response.json()["estado"] == "asignada"


@pytest.mark.asyncio
async def test_tomar_delivery_ya_asignado_rechazado(
    client: AsyncClient, producto_test: Producto
):
    order = await _hacer_checkout(client, producto_test)
    await client.post(f"/deliveries/{order['id']}/tomar")

    response = await client.post(f"/deliveries/{order['id']}/tomar")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_mis_asignados_despues_de_tomar(
    client: AsyncClient, producto_test: Producto
):
    order = await _hacer_checkout(client, producto_test)
    await client.post(f"/deliveries/{order['id']}/tomar")

    response = await client.get("/deliveries/mis-asignados")
    assert response.status_code == 200
    ids = [d["id"] for d in response.json()]
    assert order["id"] in ids


@pytest.mark.asyncio
async def test_entregar_pedido_cambia_estado(
    client: AsyncClient, producto_test: Producto
):
    order = await _hacer_checkout(client, producto_test)
    await client.post(f"/deliveries/{order['id']}/tomar")

    response = await client.post(f"/deliveries/{order['id']}/entregar")
    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "entregada"
    assert data["fecha_entrega"] is not None


@pytest.mark.asyncio
async def test_entregar_sin_tomar_rechazado(
    client: AsyncClient, producto_test: Producto
):
    order = await _hacer_checkout(client, producto_test)

    response = await client.post(f"/deliveries/{order['id']}/entregar")
    assert response.status_code == 400
