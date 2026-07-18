"""Tests del endpoint /interno/debitar — pivote de la saga (idempotente)."""
import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import FIXED_USER_ID


@pytest.mark.asyncio
async def test_debitar_saldo_ok(client: AsyncClient, internal_client: AsyncClient):
    await client.post("/billetera/cargar", json={"monto": 1000.0})

    message_id = str(uuid.uuid4())
    response = await internal_client.post(
        "/interno/debitar",
        json={
            "message_id": message_id,
            "usuario_id": str(FIXED_USER_ID),
            "monto": 300.0,
            "descripcion": "Compra de prueba",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["saldo_resultante"] == 700.0
    assert data["error"] is None


@pytest.mark.asyncio
async def test_debitar_saldo_idempotente(client: AsyncClient, internal_client: AsyncClient):
    """El mismo message_id no debe debitar dos veces."""
    await client.post("/billetera/cargar", json={"monto": 1000.0})

    message_id = str(uuid.uuid4())
    cmd = {
        "message_id": message_id,
        "usuario_id": str(FIXED_USER_ID),
        "monto": 200.0,
        "descripcion": "Pago saga checkout",
    }

    r1 = await internal_client.post("/interno/debitar", json=cmd)
    assert r1.status_code == 200
    assert r1.json()["ok"] is True
    assert r1.json()["saldo_resultante"] == 800.0

    # Mismo message_id → resultado idéntico, saldo NO se reduce de nuevo
    r2 = await internal_client.post("/interno/debitar", json=cmd)
    assert r2.status_code == 200
    assert r2.json()["ok"] is True
    assert r2.json()["saldo_resultante"] == 800.0

    # Verificar en la billetera pública que el saldo es 800, no 600
    r3 = await client.get("/billetera")
    assert r3.json()["saldo"] == 800.0


@pytest.mark.asyncio
async def test_debitar_saldo_insuficiente(client: AsyncClient, internal_client: AsyncClient):
    await client.post("/billetera/cargar", json={"monto": 50.0})

    response = await internal_client.post(
        "/interno/debitar",
        json={
            "message_id": str(uuid.uuid4()),
            "usuario_id": str(FIXED_USER_ID),
            "monto": 200.0,
            "descripcion": "Pago excesivo",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["error"] is not None
    assert "insuficiente" in data["error"].lower()
    assert data["saldo_resultante"] == 50.0


@pytest.mark.asyncio
async def test_debitar_registra_transaccion(client: AsyncClient, internal_client: AsyncClient):
    await client.post("/billetera/cargar", json={"monto": 500.0})

    await internal_client.post(
        "/interno/debitar",
        json={
            "message_id": str(uuid.uuid4()),
            "usuario_id": str(FIXED_USER_ID),
            "monto": 150.0,
            "descripcion": "Compra checkout",
        },
    )

    historial = await client.get("/billetera/historial")
    transacciones = historial.json()["transacciones"]
    tipos = [t["tipo"] for t in transacciones]
    assert "compra" in tipos
