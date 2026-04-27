import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_billetera_se_crea_automaticamente(client: AsyncClient):
    response = await client.get("/billetera")
    assert response.status_code == 200
    data = response.json()
    assert data["saldo"] == 0.0
    assert data["moneda"] == "ARS"


@pytest.mark.asyncio
async def test_cargar_saldo(client: AsyncClient):
    await client.get("/billetera")  # asegura que existe
    response = await client.post("/billetera/cargar", json={"monto": 5000.0})
    assert response.status_code == 200
    assert response.json()["saldo"] == 5000.0


@pytest.mark.asyncio
async def test_cargar_saldo_acumula(client: AsyncClient):
    await client.post("/billetera/cargar", json={"monto": 1000.0})
    response = await client.post("/billetera/cargar", json={"monto": 500.0})
    assert response.status_code == 200
    assert response.json()["saldo"] == 1500.0


@pytest.mark.asyncio
async def test_cargar_saldo_monto_negativo_rechazado(client: AsyncClient):
    response = await client.post("/billetera/cargar", json={"monto": -100.0})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cargar_saldo_supera_limite(client: AsyncClient):
    response = await client.post("/billetera/cargar", json={"monto": 999999999.0})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_historial_refleja_cargas(client: AsyncClient):
    await client.post("/billetera/cargar", json={"monto": 200.0})
    await client.post("/billetera/cargar", json={"monto": 300.0})

    response = await client.get("/billetera/historial")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    tipos = [t["tipo"] for t in data["transacciones"]]
    assert all(t == "carga" for t in tipos)
