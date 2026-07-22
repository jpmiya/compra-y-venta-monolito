"""Tests del ABM de productos — incluye la validación de dirección contra Identidad
(antes un SELECT local, ahora resuelta vía el cliente de Identidad) y la
composición síncrona de la dirección del punto de venta en las respuestas."""
import pytest
from httpx import AsyncClient

from app.adapters.persistence.models import Categoria, Producto
from tests.conftest import (
    FIXED_DIRECCION_ID,
    DIRECCION_AJENA_ID,
    DIRECCION_INACTIVA_ID,
)


@pytest.mark.asyncio
async def test_listar_categorias(client: AsyncClient, categoria_test: Categoria):
    response = await client.get("/productos/categorias")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(c["nombre"] == categoria_test.nombre for c in data)


@pytest.mark.asyncio
async def test_obtener_producto_por_id(client: AsyncClient, producto_test: Producto):
    response = await client.get(f"/productos/{producto_test.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["nombre"] == producto_test.nombre
    assert data["sku"] == producto_test.sku
    # La dirección se compone llamando a Identidad (no vive en la BD de Catálogo)
    assert data["direccion_punto_venta"] is not None
    assert data["direccion_punto_venta"]["calle"] == "Av. Corrientes"


@pytest.mark.asyncio
async def test_obtener_producto_inexistente(client: AsyncClient):
    response = await client.get("/productos/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_crear_producto(client: AsyncClient, categoria_test: Categoria):
    payload = {
        "nombre": "Producto Nuevo",
        "descripcion": "Una descripción",
        "precio": 150.0,
        "categoria_id": str(categoria_test.id),
        "stock": 10,
        "sku": "SKU-NEW-001",
        "imagenes": ["imagen1.jpg"],
        "direccion_punto_venta_id": str(FIXED_DIRECCION_ID),
    }
    response = await client.post("/productos", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["nombre"] == "Producto Nuevo"
    assert data["sku"] == "SKU-NEW-001"
    assert data["activo"] is True
    assert data["stock"] == 10
    assert data["stock_reservado"] == 0
    assert data["stock_disponible"] == 10


@pytest.mark.asyncio
async def test_crear_producto_sku_duplicado(
    client: AsyncClient, producto_test: Producto, categoria_test: Categoria
):
    payload = {
        "nombre": "Producto Repetido",
        "precio": 100.0,
        "categoria_id": str(categoria_test.id),
        "stock": 5,
        "sku": producto_test.sku,
        "imagenes": ["img.jpg"],
        "direccion_punto_venta_id": str(FIXED_DIRECCION_ID),
    }
    response = await client.post("/productos", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_crear_producto_direccion_ajena(client: AsyncClient, categoria_test: Categoria):
    """La dirección existe en Identidad pero pertenece a otra persona → 400."""
    payload = {
        "nombre": "Producto Inválido",
        "precio": 100.0,
        "categoria_id": str(categoria_test.id),
        "stock": 5,
        "sku": "SKU-BAD-001",
        "imagenes": ["img.jpg"],
        "direccion_punto_venta_id": str(DIRECCION_AJENA_ID),
    }
    response = await client.post("/productos", json=payload)
    assert response.status_code == 400
    assert "no pertenece" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_crear_producto_direccion_inactiva(client: AsyncClient, categoria_test: Categoria):
    payload = {
        "nombre": "Producto Inválido",
        "precio": 100.0,
        "categoria_id": str(categoria_test.id),
        "stock": 5,
        "sku": "SKU-BAD-002",
        "imagenes": ["img.jpg"],
        "direccion_punto_venta_id": str(DIRECCION_INACTIVA_ID),
    }
    response = await client.post("/productos", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_actualizar_producto(client: AsyncClient, producto_test: Producto):
    response = await client.put(
        f"/productos/{producto_test.id}",
        json={"precio": 1500.0, "stock": 20},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["precio"] == 1500.0
    assert data["stock"] == 20


@pytest.mark.asyncio
async def test_eliminar_producto_soft_delete(client: AsyncClient, producto_test: Producto):
    response = await client.delete(f"/productos/{producto_test.id}")
    assert response.status_code == 204
    # Baja lógica: el producto ya no se sirve
    response = await client.get(f"/productos/{producto_test.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_agregar_resena_actualiza_promedio(client: AsyncClient, producto_test: Producto):
    r1 = await client.post(
        f"/productos/{producto_test.id}/resena",
        json={"calificacion": 5, "comentario": "Excelente"},
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"/productos/{producto_test.id}/resena",
        json={"calificacion": 3},
    )
    assert r2.status_code == 201

    detalle = await client.get(f"/productos/{producto_test.id}")
    assert detalle.json()["calificacion_promedio"] == 4.0
