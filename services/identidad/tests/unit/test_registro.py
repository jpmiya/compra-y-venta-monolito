import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from unittest.mock import patch

from app.core.dependencies import get_db
from app.main import app

from .. import conftest as _conftest_module  # noqa: F401 — asegura carga de fixtures compartidas

NUEVO_FIREBASE_UID = "firebase-uid-self-registro"
NUEVO_EMAIL = "nuevo@example.com"


@pytest_asyncio.fixture
async def client_sin_usuario() -> AsyncClient:
    """Cliente con token de Firebase válido pero SIN usuario local — el caso
    que este endpoint existe para resolver."""
    request_engine = create_async_engine(_conftest_module.TEST_DATABASE_URL)
    request_session_factory = async_sessionmaker(request_engine, expire_on_commit=False)

    async def _override_db():
        async with request_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db

    with patch(
        "app.core.dependencies.verify_firebase_token",
        return_value={"uid": NUEVO_FIREBASE_UID, "email": NUEVO_EMAIL},
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {NUEVO_FIREBASE_UID}"},
        ) as ac:
            yield ac

    app.dependency_overrides.clear()
    await request_engine.dispose()


@pytest.mark.asyncio
async def test_registro_self_crea_persona_y_usuario(client_sin_usuario: AsyncClient):
    response = await client_sin_usuario.post(
        "/registro",
        json={
            "nombre_completo": "Nuevo Usuario",
            "documento_identidad": "55555555",
            "telefono": "1122334455",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["persona"]["nombre_completo"] == "Nuevo Usuario"
    assert data["usuario"]["email"] == NUEVO_EMAIL
    assert data["usuario"]["firebase_uid"] == NUEVO_FIREBASE_UID
    assert data["usuario"]["persona_id"] == data["persona"]["id"]


@pytest.mark.asyncio
async def test_registro_self_permite_usar_endpoints_protegidos_despues(
    client_sin_usuario: AsyncClient,
):
    registro = await client_sin_usuario.post(
        "/registro",
        json={"nombre_completo": "Usuario Activo", "documento_identidad": "66666666"},
    )
    assert registro.status_code == 201

    listado = await client_sin_usuario.get("/personas")
    assert listado.status_code == 200


@pytest.mark.asyncio
async def test_registro_self_rechaza_firebase_uid_duplicado(client_sin_usuario: AsyncClient):
    payload = {"nombre_completo": "Primero", "documento_identidad": "77777777"}
    primero = await client_sin_usuario.post("/registro", json=payload)
    assert primero.status_code == 201

    segundo = await client_sin_usuario.post(
        "/registro",
        json={"nombre_completo": "Segundo", "documento_identidad": "88888888"},
    )
    assert segundo.status_code == 409


@pytest.mark.asyncio
async def test_registro_self_rechaza_documento_duplicado(client_sin_usuario: AsyncClient):
    await client_sin_usuario.post(
        "/registro",
        json={"nombre_completo": "Original", "documento_identidad": "12121212"},
    )

    with patch(
        "app.core.dependencies.verify_firebase_token",
        return_value={"uid": "otro-uid", "email": "otro@example.com"},
    ):
        response = await client_sin_usuario.post(
            "/registro",
            json={"nombre_completo": "Duplicado", "documento_identidad": "12121212"},
        )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_registro_self_sin_email_en_token_devuelve_400(client_sin_usuario: AsyncClient):
    with patch(
        "app.core.dependencies.verify_firebase_token",
        return_value={"uid": "uid-sin-email"},
    ):
        response = await client_sin_usuario.post(
            "/registro",
            json={"nombre_completo": "Sin Email", "documento_identidad": "13131313"},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_registro_self_requiere_token_valido():
    request_engine = create_async_engine(_conftest_module.TEST_DATABASE_URL)
    request_session_factory = async_sessionmaker(request_engine, expire_on_commit=False)

    async def _override_db():
        async with request_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/registro",
                json={"nombre_completo": "Sin Token", "documento_identidad": "14141414"},
            )
        assert response.status_code in (401, 403)
    finally:
        app.dependency_overrides.clear()
        await request_engine.dispose()
