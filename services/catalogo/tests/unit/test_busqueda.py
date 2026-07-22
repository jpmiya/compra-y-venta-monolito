"""Tests de búsqueda — solo productos activos con stock DISPONIBLE (físico - reservado),
con la dirección del punto de venta compuesta desde Identidad."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.persistence.models import Categoria, Producto
from tests.conftest import FIXED_USER_ID, FIXED_DIRECCION_ID


@pytest.mark.asyncio
async def test_buscar_por_texto(client: AsyncClient, producto_test: Producto):
    response = await client.get("/busqueda", params={"q": "Notebook"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["nombre"] == producto_test.nombre


@pytest.mark.asyncio
async def test_buscar_sin_resultados(client: AsyncClient, producto_test: Producto):
    response = await client.get("/busqueda", params={"q": "Heladera"})
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_buscar_filtro_precio(client: AsyncClient, producto_test: Producto):
    response = await client.get("/busqueda", params={"precio_min": 2000})
    assert response.json()["total"] == 0

    response = await client.get(
        "/busqueda", params={"precio_min": 500, "precio_max": 1500}
    )
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_busqueda_compone_direccion(client: AsyncClient, producto_test: Producto):
    """El listado devuelve la dirección completa del punto de venta (dato de Identidad)."""
    response = await client.get("/busqueda")
    item = response.json()["items"][0]
    assert item["direccion_punto_venta"] is not None
    assert item["direccion_punto_venta"]["ciudad"] == "Buenos Aires"
    assert item["direccion_punto_venta"]["calle"] == "Av. Corrientes"


@pytest.mark.asyncio
async def test_busqueda_excluye_sin_stock_fisico(
    client: AsyncClient, db: AsyncSession, categoria_test: Categoria
):
    producto = Producto(
        nombre="Producto Agotado",
        precio=100.0,
        stock=0,
        sku="SKU-AGOTADO",
        imagenes=["img.jpg"],
        vendedor_id=FIXED_USER_ID,
        direccion_punto_venta_id=FIXED_DIRECCION_ID,
        categoria_id=categoria_test.id,
    )
    db.add(producto)
    await db.commit()

    response = await client.get("/busqueda", params={"q": "Agotado"})
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_busqueda_excluye_stock_totalmente_reservado(
    client: AsyncClient, db: AsyncSession, categoria_test: Categoria
):
    """Un producto con todo su stock reservado por sagas en curso no está disponible."""
    producto = Producto(
        nombre="Producto Reservado",
        precio=100.0,
        stock=5,
        stock_reservado=5,
        sku="SKU-RESERVADO",
        imagenes=["img.jpg"],
        vendedor_id=FIXED_USER_ID,
        direccion_punto_venta_id=FIXED_DIRECCION_ID,
        categoria_id=categoria_test.id,
    )
    db.add(producto)
    await db.commit()

    response = await client.get("/busqueda", params={"q": "Reservado"})
    assert response.json()["total"] == 0
