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
    "postgresql+asyncpg://postgres:pass123@localhost:5441/delivery_test",
)
os.environ.setdefault("BROKER_ENABLED", "false")

from app.core.database import Base
from app.core.dependencies import get_db, get_current_usuario_id
from app.main import app
from app.adapters.persistence.models import DeliveryOrder, MensajeProcesado  # noqa: F401

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:pass123@localhost:5441/delivery_test",
)

# UUIDs fijos (resueltos desde Identidad en producción)
FIXED_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")   # entregador autenticado
COMPRADOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
OTRO_ENTREGADOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
PRODUCTO_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")
DIRECCION_PV_ID = uuid.UUID("00000000-0000-0000-0000-000000000005")


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
                text("TRUNCATE TABLE mensajes_procesados, delivery_orders CASCADE")
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
async def session_factory():
    """Factory de sesiones para el consumer (que abre su propia sesión por mensaje)."""
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Cliente con entregador autenticado (get_current_usuario_id → FIXED_USER_ID)."""
    request_engine = create_async_engine(TEST_DATABASE_URL)
    request_session_factory = async_sessionmaker(request_engine, expire_on_commit=False)

    async def _override_db():
        async with request_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_usuario_id] = lambda: FIXED_USER_ID

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    await request_engine.dispose()


@pytest_asyncio.fixture
async def delivery_pendiente(db: AsyncSession) -> DeliveryOrder:
    delivery = DeliveryOrder(
        comprador_id=COMPRADOR_ID,
        producto_id=PRODUCTO_ID,
        cantidad=2,
        precio_unitario=500.0,
        direccion_entrega="Av. Test 999",
        direccion_punto_venta_id=DIRECCION_PV_ID,
    )
    db.add(delivery)
    await db.commit()
    await db.refresh(delivery)
    return delivery
