"""Tests para los endpoints /interno/ que usan otros microservicios."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.persistence.models import Persona, Usuario, Direccion


@pytest.mark.asyncio
async def test_get_usuario_por_id(internal_client: AsyncClient, usuario_test: Usuario):
    response = await internal_client.get(f"/interno/usuarios/{usuario_test.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(usuario_test.id)
    assert data["firebase_uid"] == usuario_test.firebase_uid
    assert data["estado"] == "activo"


@pytest.mark.asyncio
async def test_get_usuario_por_firebase_uid(internal_client: AsyncClient, usuario_test: Usuario):
    response = await internal_client.get(
        f"/interno/usuarios/by-firebase/{usuario_test.firebase_uid}"
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(usuario_test.id)


@pytest.mark.asyncio
async def test_get_usuario_inexistente(internal_client: AsyncClient):
    response = await internal_client.get(
        "/interno/usuarios/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_direccion(
    internal_client: AsyncClient, db: AsyncSession, usuario_test: Usuario
):
    direccion = Direccion(
        persona_id=usuario_test.persona_id,
        calle="Av. Rivadavia",
        numero="5000",
        ciudad="Buenos Aires",
        provincia="CABA",
        activa=True,
    )
    db.add(direccion)
    await db.commit()
    await db.refresh(direccion)

    response = await internal_client.get(f"/interno/direcciones/{direccion.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["calle"] == "Av. Rivadavia"
    assert data["activa"] is True


@pytest.mark.asyncio
async def test_get_firebase_uid_inexistente(internal_client: AsyncClient):
    response = await internal_client.get("/interno/usuarios/by-firebase/uid-que-no-existe")
    assert response.status_code == 404
