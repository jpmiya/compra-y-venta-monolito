from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.database import Base
from app.core.dependencies import get_db
from app.main import app
from app.modules.admin.models import Direccion, Persona, Usuario
from app.modules.productos.models import Categoria, Producto

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/compra_venta_test"

_engine = create_async_engine(TEST_DATABASE_URL)
_TestSession = async_sessionmaker(_engine, expire_on_commit=False)

TEST_FIREBASE_UID = "test-firebase-uid-001"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    async with _TestSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def usuario_test(db: AsyncSession) -> Usuario:
    """Crea una Persona y Usuario de prueba con el UID de Firebase mockeado."""
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
async def client(db: AsyncSession, usuario_test: Usuario) -> AsyncClient:
    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db

    # Mockear verify_firebase_token para que devuelva el UID de prueba
    with patch(
        "app.core.firebase.verify_firebase_token",
        return_value={"uid": TEST_FIREBASE_UID},
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


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
