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


@pytest.mark.asyncio
async def test_get_direcciones_batch(
    internal_client: AsyncClient, db: AsyncSession, usuario_test: Usuario
):
    """Resolución batch de direcciones (composición síncrona desde Catálogo)."""
    d1 = Direccion(
        persona_id=usuario_test.persona_id,
        calle="Av. Santa Fe", numero="1000",
        ciudad="Buenos Aires", provincia="CABA", activa=True,
    )
    d2 = Direccion(
        persona_id=usuario_test.persona_id,
        calle="Av. Cabildo", numero="2000",
        ciudad="Buenos Aires", provincia="CABA", activa=True,
    )
    db.add_all([d1, d2])
    await db.commit()
    await db.refresh(d1)
    await db.refresh(d2)

    response = await internal_client.get(
        "/interno/direcciones",
        params=[("ids", str(d1.id)), ("ids", str(d2.id))],
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    calles = {d["calle"] for d in data}
    assert calles == {"Av. Santa Fe", "Av. Cabildo"}


@pytest.mark.asyncio
async def test_get_direcciones_batch_ignora_inexistentes(internal_client: AsyncClient):
    """IDs que no existen simplemente no vienen en la respuesta (no rompe el listado)."""
    response = await internal_client.get(
        "/interno/direcciones",
        params=[("ids", "00000000-0000-0000-0000-000000000000")],
    )
    assert response.status_code == 200
    assert response.json() == []
