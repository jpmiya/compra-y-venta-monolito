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
    "postgresql+asyncpg://postgres:pass123@localhost:5443/carrito_test",
)
os.environ.setdefault("BROKER_ENABLED", "false")

from app.core.database import Base
from app.core.dependencies import get_db, get_current_usuario_id
from app.core.http_client import get_catalogo_client, get_billetera_client
from app.main import app
from app.adapters.persistence.models import (  # noqa: F401
    Carrito,
    CarritoItem,
    SagaCheckout,
    DeliveryLog,
)

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:pass123@localhost:5443/carrito_test",
)

FIXED_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PRODUCTO_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
PRODUCTO_2_ID = uuid.UUID("00000000-0000-0000-0000-000000000011")
DIRECCION_PV_ID = uuid.UUID("00000000-0000-0000-0000-000000000020")


class FakeCatalogoClient:
    """Simula el servicio Catálogo: productos + comandos de stock idempotentes.

    Registra las llamadas (reservas/descuentos/liberaciones) para que los tests
    verifiquen la orquestación y la compensación de la saga.
    """

    def __init__(self):
        self.productos = {
            str(PRODUCTO_ID): {
                "id": str(PRODUCTO_ID),
                "activo": True,
                "precio": 1000.0,
                "stock": 10,
                "stock_reservado": 0,
                "stock_disponible": 10,
                "direccion_punto_venta_id": str(DIRECCION_PV_ID),
                "nombre": "Notebook Test",
            },
            str(PRODUCTO_2_ID): {
                "id": str(PRODUCTO_2_ID),
                "activo": True,
                "precio": 500.0,
                "stock": 5,
                "stock_reservado": 0,
                "stock_disponible": 5,
                "direccion_punto_venta_id": str(DIRECCION_PV_ID),
                "nombre": "Mouse Test",
            },
        }
        self.reservas = []      # [(message_id, items)]
        self.descuentos = []    # [(message_id, items)]
        self.liberaciones = []  # [(message_id, items)]

    async def get_producto(self, producto_id):
        return self.productos.get(str(producto_id))

    async def reservar_stock(self, message_id, saga_id, items):
        for item in items:
            producto = self.productos.get(item["producto_id"])
            if not producto:
                return {"ok": False, "error": f"Producto {item['producto_id']} no encontrado"}
            if producto["stock_disponible"] < item["cantidad"]:
                return {"ok": False, "error": f"Stock insuficiente para '{producto['nombre']}'"}
        for item in items:
            self.productos[item["producto_id"]]["stock_disponible"] -= item["cantidad"]
        self.reservas.append((message_id, items))
        return {"ok": True, "error": None}

    async def descontar_stock(self, message_id, saga_id, items):
        self.descuentos.append((message_id, items))
        return {"ok": True, "error": None}

    async def liberar_stock(self, message_id, saga_id, items):
        for item in items:
            if item["producto_id"] in self.productos:
                self.productos[item["producto_id"]]["stock_disponible"] += item["cantidad"]
        self.liberaciones.append((message_id, items))
        return {"ok": True, "error": None}


class FakeBilleteraClient:
    """Simula el pivote DebitarSaldo con saldo configurable e idempotencia real."""

    def __init__(self, saldo: float = 100000.0):
        self.saldo = saldo
        self.debitos = []  # [(message_id, monto)]
        self._procesados = {}

    async def debitar_saldo(self, message_id, usuario_id, monto, descripcion):
        clave = str(message_id)
        if clave in self._procesados:
            return self._procesados[clave]
        if self.saldo < monto:
            return {"ok": False, "saldo_resultante": self.saldo, "error": "Saldo insuficiente en la billetera"}
        self.saldo -= monto
        self.debitos.append((message_id, monto))
        resultado = {"ok": True, "saldo_resultante": self.saldo, "error": None}
        self._procesados[clave] = resultado
        return resultado


class PublicadorFake:
    """Puerto de publicación fake. `fallar=True` simula el broker caído."""

    def __init__(self, fallar: bool = False):
        self.fallar = fallar
        self.publicados = []  # [(payload, reply_queue)]

    async def publicar(self, payload: str, reply_queue: str):
        if self.fallar:
            raise ConnectionError("Broker caído (simulado)")
        self.publicados.append((payload, reply_queue))


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
                text(
                    "TRUNCATE TABLE delivery_log, sagas_checkout, carrito_items, carritos CASCADE"
                )
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
def fake_catalogo() -> FakeCatalogoClient:
    return FakeCatalogoClient()


@pytest_asyncio.fixture
def fake_billetera() -> FakeBilleteraClient:
    return FakeBilleteraClient()


@pytest_asyncio.fixture
async def client(fake_catalogo, fake_billetera) -> AsyncClient:
    """Cliente autenticado con Catálogo y Billetera fakes inyectados."""
    request_engine = create_async_engine(TEST_DATABASE_URL)
    request_session_factory = async_sessionmaker(request_engine, expire_on_commit=False)

    async def _override_db():
        async with request_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_usuario_id] = lambda: FIXED_USER_ID
    app.dependency_overrides[get_catalogo_client] = lambda: fake_catalogo
    app.dependency_overrides[get_billetera_client] = lambda: fake_billetera

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    await request_engine.dispose()
