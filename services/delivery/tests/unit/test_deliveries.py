"""Tests del ciclo de vida del delivery: pendiente → asignada → entregada."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.persistence.models import DeliveryOrder
from tests.conftest import FIXED_USER_ID, OTRO_ENTREGADOR_ID


@pytest.mark.asyncio
async def test_listar_pendientes(client: AsyncClient, delivery_pendiente: DeliveryOrder):
    response = await client.get("/deliveries")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["estado"] == "pendiente"


@pytest.mark.asyncio
async def test_obtener_detalle(client: AsyncClient, delivery_pendiente: DeliveryOrder):
    response = await client.get(f"/deliveries/{delivery_pendiente.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(delivery_pendiente.id)


@pytest.mark.asyncio
async def test_delivery_inexistente(client: AsyncClient):
    response = await client.get("/deliveries/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_tomar_delivery(client: AsyncClient, delivery_pendiente: DeliveryOrder):
    response = await client.post(f"/deliveries/{delivery_pendiente.id}/tomar")
    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "asignada"
    assert data["entregador_id"] == str(FIXED_USER_ID)
    assert data["fecha_asignacion"] is not None

    # Ya no aparece entre los pendientes, sí entre mis asignados
    pendientes = await client.get("/deliveries")
    assert len(pendientes.json()) == 0
    asignados = await client.get("/deliveries/mis-asignados")
    assert len(asignados.json()) == 1


@pytest.mark.asyncio
async def test_tomar_delivery_ya_asignado(client: AsyncClient, delivery_pendiente: DeliveryOrder):
    await client.post(f"/deliveries/{delivery_pendiente.id}/tomar")
    response = await client.post(f"/deliveries/{delivery_pendiente.id}/tomar")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_entregar_delivery(client: AsyncClient, delivery_pendiente: DeliveryOrder):
    await client.post(f"/deliveries/{delivery_pendiente.id}/tomar")
    response = await client.post(f"/deliveries/{delivery_pendiente.id}/entregar")
    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "entregada"
    assert data["fecha_entrega"] is not None


@pytest.mark.asyncio
async def test_entregar_sin_tomar(client: AsyncClient, delivery_pendiente: DeliveryOrder):
    response = await client.post(f"/deliveries/{delivery_pendiente.id}/entregar")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_entregar_por_otro_entregador(
    client: AsyncClient, db: AsyncSession, delivery_pendiente: DeliveryOrder
):
    """Solo el entregador asignado puede marcar la entrega."""
    from datetime import datetime, timezone

    delivery_pendiente.entregador_id = OTRO_ENTREGADOR_ID
    delivery_pendiente.estado = "asignada"
    delivery_pendiente.fecha_asignacion = datetime.now(timezone.utc)
    await db.commit()

    response = await client.post(f"/deliveries/{delivery_pendiente.id}/entregar")
    assert response.status_code == 400
    assert "asignado" in response.json()["detail"].lower()
