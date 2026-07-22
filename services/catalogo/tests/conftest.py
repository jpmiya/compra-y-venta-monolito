import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Debe setearse antes de que pydantic-settings cargue Settings()
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:pass123@localhost:5439/catalogo_test",
)

from app.core.database import Base
from app.core.dependencies import get_db, get_current_usuario
from app.core.http_client import get_identidad_client
from app.main import app
from app.adapters.persistence.models import Categoria, Producto, Resena, MensajeProcesado  # noqa: F401

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:pass123@localhost:5439/catalogo_test",
)

# Identidades fijas que simulan lo que resolvería el servicio Identidad
FIXED_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
FIXED_PERSONA_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
FIXED_DIRECCION_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
DIRECCION_AJENA_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")
DIRECCION_INACTIVA_ID = uuid.UUID("00000000-0000-0000-0000-000000000005")

FIXED_USUARIO = {
    "id": str(FIXED_USER_ID),
    "persona_id": str(FIXED_PERSONA_ID),
    "estado": "activo",
}

DIRECCIONES_FAKE = {
    str(FIXED_DIRECCION_ID): {
        "id": str(FIXED_DIRECCION_ID),
        "persona_id": str(FIXED_PERSONA_ID),
        "calle": "Av. Corrientes",
        "numero": "1234",
        "ciudad": "Buenos Aires",
        "provincia": "CABA",
        "descripcion": "Local test",
        "activa": True,
    },
    str(DIRECCION_AJENA_ID): {
        "id": str(DIRECCION_AJENA_ID),
        "persona_id": str(uuid.uuid4()),  # otra persona
        "calle": "Calle Falsa",
        "numero": "123",
        "ciudad": "Springfield",
        "provincia": "BA",
        "descripcion": None,
        "activa": True,
    },
    str(DIRECCION_INACTIVA_ID): {
        "id": str(DIRECCION_INACTIVA_ID),
        "persona_id": str(FIXED_PERSONA_ID),
        "calle": "Vieja",
        "numero": "1",
        "ciudad": "CABA",
        "provincia": "CABA",
        "descripcion": None,
        "activa": False,
    },
}


class FakeIdentidadClient:
    """Adaptador fake de Identidad: mismas respuestas que los endpoints /interno reales."""

    async def get_usuario_by_firebase_uid(self, firebase_uid: str):
        return FIXED_USUARIO

    async def get_direccion(self, direccion_id: uuid.UUID):
        return DIRECCIONES_FAKE.get(str(direccion_id))

    async def get_direcciones(self, direccion_ids):
        return [
            DIRECCIONES_FAKE[str(d)]
            for d in direccion_ids
            if str(d) in DIRECCIONES_FAKE
        ]


async def _run_on_engine(coro_fn):
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await coro_fn(conn)
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    async def _create(conn):
        await conn.run_sync(Base.metadata.create_all)

    async def _drop(conn):
        await conn.run_sync(Base.metadata.drop_all)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_run_on_engine(_create))
    yield
    loop.run_until_complete(_run_on_engine(_drop))
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def limpiar_tablas():
    yield
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("TRUNCATE TABLE mensajes_procesados, resenas, productos, categorias CASCADE")
            )
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Cliente con usuario autenticado (Firebase + Identidad mockeados)."""
    request_engine = create_async_engine(TEST_DATABASE_URL)
    request_session_factory = async_sessionmaker(request_engine, expire_on_commit=False)

    async def _override_db():
        async with request_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_usuario] = lambda: FIXED_USUARIO
    app.dependency_overrides[get_identidad_client] = lambda: FakeIdentidadClient()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    await request_engine.dispose()


@pytest_asyncio.fixture
async def internal_client() -> AsyncClient:
    """Cliente para endpoints /interno/ (sin auth de usuario)."""
    request_engine = create_async_engine(TEST_DATABASE_URL)
    request_session_factory = async_sessionmaker(request_engine, expire_on_commit=False)

    async def _override_db():
        async with request_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_identidad_client] = lambda: FakeIdentidadClient()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    await request_engine.dispose()


# --- Fixtures de datos ---

@pytest_asyncio.fixture
async def categoria_test(db: AsyncSession) -> Categoria:
    categoria = Categoria(nombre="Electrónica", descripcion="Productos electrónicos")
    db.add(categoria)
    await db.commit()
    await db.refresh(categoria)
    return categoria


@pytest_asyncio.fixture
async def producto_test(db: AsyncSession, categoria_test: Categoria) -> Producto:
    producto = Producto(
        nombre="Notebook Test",
        descripcion="Una notebook de prueba",
        precio=1000.0,
        stock=10,
        sku="SKU-TEST-001",
        imagenes=["img1.jpg"],
        vendedor_id=FIXED_USER_ID,
        direccion_punto_venta_id=FIXED_DIRECCION_ID,
        categoria_id=categoria_test.id,
    )
    db.add(producto)
    await db.commit()
    await db.refresh(producto)
    return producto
