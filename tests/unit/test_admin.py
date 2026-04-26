import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_crear_persona(client: AsyncClient):
    response = await client.post(
        "/personas",
        json={
            "nombre_completo": "Juan Perez",
            "documento_identidad": "12345678",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["nombre_completo"] == "Juan Perez"
    assert data["documento_identidad"] == "12345678"
    assert data["estado"] == "activo"


@pytest.mark.asyncio
async def test_crear_persona_documento_duplicado(client: AsyncClient):
    payload = {"nombre_completo": "Ana Lopez", "documento_identidad": "11111111"}
    await client.post("/personas", json=payload)
    response = await client.post("/personas", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_listar_personas(client: AsyncClient):
    response = await client.get("/personas")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_obtener_persona_inexistente(client: AsyncClient):
    response = await client.get("/personas/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_crear_usuario_para_persona(client: AsyncClient):
    persona_resp = await client.post(
        "/personas",
        json={"nombre_completo": "Maria Garcia", "documento_identidad": "22222222"},
    )
    persona_id = persona_resp.json()["id"]

    response = await client.post(
        f"/personas/{persona_id}/usuarios",
        json={"email": "maria@example.com", "firebase_uid": "firebase-uid-maria"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == "maria@example.com"
    assert response.json()["firebase_uid"] == "firebase-uid-maria"


@pytest.mark.asyncio
async def test_crear_direccion_para_persona(client: AsyncClient):
    persona_resp = await client.post(
        "/personas",
        json={"nombre_completo": "Carlos Ruiz", "documento_identidad": "33333333"},
    )
    persona_id = persona_resp.json()["id"]

    response = await client.post(
        f"/personas/{persona_id}/direcciones",
        json={
            "calle": "Av. Corrientes",
            "numero": "1234",
            "ciudad": "Buenos Aires",
            "provincia": "CABA",
            "descripcion": "Local comercial",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["calle"] == "Av. Corrientes"
    assert data["activa"] is True


@pytest.mark.asyncio
async def test_baja_logica_persona(client: AsyncClient):
    persona_resp = await client.post(
        "/personas",
        json={"nombre_completo": "Para Borrar", "documento_identidad": "44444444"},
    )
    persona_id = persona_resp.json()["id"]

    delete_resp = await client.delete(f"/personas/{persona_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/personas/{persona_id}")
    assert get_resp.json()["estado"] == "inactivo"
