import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import Direccion
from app.modules.productos.models import Categoria, Producto


@pytest.mark.asyncio
async def test_listar_categorias(
    client: AsyncClient, categoria_test: Categoria
):
    response = await client.get("/productos/categorias")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(c["nombre"] == categoria_test.nombre for c in data)


@pytest.mark.asyncio
async def test_obtener_producto_por_id(
    client: AsyncClient, producto_test: Producto
):
    response = await client.get(f"/productos/{producto_test.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["nombre"] == producto_test.nombre
    assert data["sku"] == producto_test.sku


@pytest.mark.asyncio
async def test_obtener_producto_inexistente(client: AsyncClient):
    response = await client.get("/productos/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_crear_producto(
    client: AsyncClient,
    direccion_test: Direccion,
    categoria_test: Categoria,
):
    payload = {
        "nombre": "Producto Nuevo",
        "descripcion": "Una descripción",
        "precio": 150.0,
        "categoria_id": str(categoria_test.id),
        "stock": 10,
        "sku": "SKU-NEW-001",
        "imagenes": ["imagen1.jpg"],
        "direccion_punto_venta_id": str(direccion_test.id),
    }
    response = await client.post("/productos", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["nombre"] == "Producto Nuevo"
    assert data["sku"] == "SKU-NEW-001"
    assert data["activo"] is True


@pytest.mark.asyncio
async def test_crear_producto_sku_duplicado(
    client: AsyncClient,
    direccion_test: Direccion,
    categoria_test: Categoria,
    producto_test: Producto,
):
    payload = {
        "nombre": "Otro producto",
        "precio": 100.0,
        "categoria_id": str(categoria_test.id),
        "stock": 1,
        "sku": producto_test.sku,
        "imagenes": ["img.jpg"],
        "direccion_punto_venta_id": str(direccion_test.id),
    }
    response = await client.post("/productos", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_crear_producto_nombre_muy_corto(
    client: AsyncClient,
    direccion_test: Direccion,
    categoria_test: Categoria,
):
    payload = {
        "nombre": "abc",
        "precio": 100.0,
        "categoria_id": str(categoria_test.id),
        "stock": 1,
        "sku": "SKU-SHORT",
        "imagenes": ["img.jpg"],
        "direccion_punto_venta_id": str(direccion_test.id),
    }
    response = await client.post("/productos", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_crear_producto_precio_negativo(
    client: AsyncClient,
    direccion_test: Direccion,
    categoria_test: Categoria,
):
    payload = {
        "nombre": "Producto inválido",
        "precio": -10.0,
        "categoria_id": str(categoria_test.id),
        "stock": 1,
        "sku": "SKU-NEG",
        "imagenes": ["img.jpg"],
        "direccion_punto_venta_id": str(direccion_test.id),
    }
    response = await client.post("/productos", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_crear_producto_sin_imagenes(
    client: AsyncClient,
    direccion_test: Direccion,
    categoria_test: Categoria,
):
    payload = {
        "nombre": "Producto sin foto",
        "precio": 100.0,
        "categoria_id": str(categoria_test.id),
        "stock": 1,
        "sku": "SKU-NOIMG",
        "imagenes": [],
        "direccion_punto_venta_id": str(direccion_test.id),
    }
    response = await client.post("/productos", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_actualizar_producto(
    client: AsyncClient, producto_test: Producto
):
    response = await client.put(
        f"/productos/{producto_test.id}",
        json={"precio": 999.99, "stock": 50},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["precio"] == 999.99
    assert data["stock"] == 50


@pytest.mark.asyncio
async def test_actualizar_producto_inexistente(client: AsyncClient):
    response = await client.put(
        "/productos/00000000-0000-0000-0000-000000000000",
        json={"precio": 1.0},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_eliminar_producto_es_baja_logica(
    client: AsyncClient,
    db: AsyncSession,
    producto_test: Producto,
):
    delete_resp = await client.delete(f"/productos/{producto_test.id}")
    assert delete_resp.status_code == 204

    await db.refresh(producto_test)
    assert producto_test.activo is False

    get_resp = await client.get(f"/productos/{producto_test.id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_agregar_resena(
    client: AsyncClient, producto_test: Producto
):
    response = await client.post(
        f"/productos/{producto_test.id}/resena",
        json={"calificacion": 5, "comentario": "Excelente"},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_resena_actualiza_calificacion_promedio(
    client: AsyncClient,
    db: AsyncSession,
    producto_test: Producto,
):
    await client.post(
        f"/productos/{producto_test.id}/resena",
        json={"calificacion": 4},
    )
    await client.post(
        f"/productos/{producto_test.id}/resena",
        json={"calificacion": 2},
    )

    await db.refresh(producto_test)
    assert producto_test.calificacion_promedio == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_resena_calificacion_invalida_rechazada(
    client: AsyncClient, producto_test: Producto
):
    response = await client.post(
        f"/productos/{producto_test.id}/resena",
        json={"calificacion": 6},
    )
    assert response.status_code == 422
