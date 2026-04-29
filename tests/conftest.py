import asyncio
import os
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.database import Base
from app.core.dependencies import get_db
from app.main import app
from app.modules.admin.models import Direccion, Persona, Usuario
from app.modules.notificaciones.models import Notificacion  # noqa: F401
from app.modules.productos.models import Categoria, Producto

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:pass123@localhost:5433/compra_venta_test",
)
TEST_FIREBASE_UID = "test-firebase-uid-001"


async def _run_on_engine(coro_fn):
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await coro_fn(conn)
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Crea las tablas una sola vez para toda la sesión de tests (sincrónico)."""
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
                    "TRUNCATE TABLE transacciones_billetera, billeteras, delivery_orders, "
                    "carrito_items, carritos, resenas, productos, categorias, orden_items, "
                    "ordenes, usuario_roles, usuarios, direcciones, personas, roles, "
                    "notificaciones CASCADE"
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
async def usuario_test(db: AsyncSession) -> Usuario:
    persona = Persona(
        nombre_completo="Usuario Test",
        documento_identidad="99999999",
        estado="activo",
    )
    db.add(persona)
    await db.flush()

    usuario = Usuario(
        persona_id=persona.id,
        email="test@example.com",
        firebase_uid=TEST_FIREBASE_UID,
        estado="activo",
    )
    db.add(usuario)
    await db.commit()
    await db.refresh(usuario)
    return usuario


@pytest_asyncio.fixture
async def client(usuario_test: Usuario) -> AsyncClient:
    # Cada request del test recibe su propia sesión (igual que en producción)
    request_engine = create_async_engine(TEST_DATABASE_URL)
    request_session_factory = async_sessionmaker(request_engine, expire_on_commit=False)

    async def _override_db():
        async with request_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db

    with patch(
        "app.core.dependencies.verify_firebase_token",
        return_value={"uid": TEST_FIREBASE_UID},
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {TEST_FIREBASE_UID}"},
        ) as ac:
            yield ac

    app.dependency_overrides.clear()
    await request_engine.dispose()


@pytest_asyncio.fixture
async def direccion_test(db: AsyncSession, usuario_test: Usuario) -> Direccion:
    direccion = Direccion(
        persona_id=usuario_test.persona_id,
        calle="Av. Corrientes",
        numero="1234",
        ciudad="Buenos Aires",
        provincia="CABA",
        descripcion="Local test",
        activa=True,
    )
    db.add(direccion)
    await db.commit()
    await db.refresh(direccion)
    return direccion


@pytest_asyncio.fixture
async def categoria_test(db: AsyncSession) -> Categoria:
    categoria = Categoria(nombre="Electrónica", descripcion="Productos electrónicos")
    db.add(categoria)
    await db.commit()
    await db.refresh(categoria)
    return categoria


@pytest_asyncio.fixture
async def producto_test(
    db: AsyncSession,
    usuario_test: Usuario,
    direccion_test: Direccion,
    categoria_test: Categoria,
) -> Producto:
    producto = Producto(
        nombre="Notebook Test",
        descripcion="Una notebook de prueba",
        precio=1000.0,
        stock=10,
        sku="SKU-TEST-001",
        imagenes=["img1.jpg"],
        vendedor_id=usuario_test.id,
        direccion_punto_venta_id=direccion_test.id,
        categoria_id=categoria_test.id,
    )
    db.add(producto)
    await db.commit()
    await db.refresh(producto)
    return producto
