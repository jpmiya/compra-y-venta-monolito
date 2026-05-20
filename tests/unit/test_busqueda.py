import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import Direccion, Usuario
from app.modules.productos.models import Categoria, Producto


async def _crear_producto(
    db: AsyncSession,
    usuario: Usuario,
    direccion: Direccion,
    categoria: Categoria,
    *,
    nombre: str,
    precio: float,
    sku: str,
    stock: int = 5,
) -> Producto:
    producto = Producto(
        nombre=nombre,
        descripcion=f"desc {nombre}",
        precio=precio,
        stock=stock,
        sku=sku,
        imagenes=["img.jpg"],
        vendedor_id=usuario.id,
        direccion_punto_venta_id=direccion.id,
        categoria_id=categoria.id,
    )
    db.add(producto)
    await db.commit()
    await db.refresh(producto)
    return producto


@pytest.mark.asyncio
async def test_busqueda_sin_filtros_devuelve_todos(
    client: AsyncClient,
    db: AsyncSession,
    usuario_test: Usuario,
    direccion_test: Direccion,
    categoria_test: Categoria,
):
    await _crear_producto(
        db, usuario_test, direccion_test, categoria_test,
        nombre="Notebook Lenovo", precio=500.0, sku="SKU-B-1",
    )
    await _crear_producto(
        db, usuario_test, direccion_test, categoria_test,
        nombre="Mouse inalámbrico", precio=20.0, sku="SKU-B-2",
    )

    response = await client.get("/busqueda")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_busqueda_por_texto_filtra_por_nombre(
    client: AsyncClient,
    db: AsyncSession,
    usuario_test: Usuario,
    direccion_test: Direccion,
    categoria_test: Categoria,
):
    await _crear_producto(
        db, usuario_test, direccion_test, categoria_test,
        nombre="Notebook Lenovo", precio=500.0, sku="SKU-B-3",
    )
    await _crear_producto(
        db, usuario_test, direccion_test, categoria_test,
        nombre="Auriculares Sony", precio=80.0, sku="SKU-B-4",
    )

    response = await client.get("/busqueda", params={"q": "notebook"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["nombre"] == "Notebook Lenovo"


@pytest.mark.asyncio
async def test_busqueda_filtra_por_rango_de_precio(
    client: AsyncClient,
    db: AsyncSession,
    usuario_test: Usuario,
    direccion_test: Direccion,
    categoria_test: Categoria,
):
    await _crear_producto(
        db, usuario_test, direccion_test, categoria_test,
        nombre="Producto barato", precio=50.0, sku="SKU-B-5",
    )
    await _crear_producto(
        db, usuario_test, direccion_test, categoria_test,
        nombre="Producto medio", precio=500.0, sku="SKU-B-6",
    )
    await _crear_producto(
        db, usuario_test, direccion_test, categoria_test,
        nombre="Producto caro", precio=5000.0, sku="SKU-B-7",
    )

    response = await client.get(
        "/busqueda", params={"precio_min": 100, "precio_max": 1000}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["nombre"] == "Producto medio"


@pytest.mark.asyncio
async def test_busqueda_filtra_por_categoria(
    client: AsyncClient,
    db: AsyncSession,
    usuario_test: Usuario,
    direccion_test: Direccion,
    categoria_test: Categoria,
):
    otra_categoria = Categoria(nombre="Ropa", descripcion="Indumentaria")
    db.add(otra_categoria)
    await db.commit()
    await db.refresh(otra_categoria)

    await _crear_producto(
        db, usuario_test, direccion_test, categoria_test,
        nombre="Notebook X", precio=500.0, sku="SKU-B-8",
    )
    await _crear_producto(
        db, usuario_test, direccion_test, otra_categoria,
        nombre="Remera básica", precio=30.0, sku="SKU-B-9",
    )

    response = await client.get(
        "/busqueda", params={"categoria_id": str(otra_categoria.id)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["nombre"] == "Remera básica"


@pytest.mark.asyncio
async def test_busqueda_ordena_por_precio_ascendente(
    client: AsyncClient,
    db: AsyncSession,
    usuario_test: Usuario,
    direccion_test: Direccion,
    categoria_test: Categoria,
):
    await _crear_producto(
        db, usuario_test, direccion_test, categoria_test,
        nombre="Producto A", precio=300.0, sku="SKU-B-10",
    )
    await _crear_producto(
        db, usuario_test, direccion_test, categoria_test,
        nombre="Producto B", precio=100.0, sku="SKU-B-11",
    )
    await _crear_producto(
        db, usuario_test, direccion_test, categoria_test,
        nombre="Producto C", precio=200.0, sku="SKU-B-12",
    )

    response = await client.get(
        "/busqueda", params={"orden": "precio", "ascendente": "true"}
    )
    assert response.status_code == 200
    precios = [item["precio"] for item in response.json()["items"]]
    assert precios == sorted(precios)


@pytest.mark.asyncio
async def test_busqueda_excluye_productos_sin_stock(
    client: AsyncClient,
    db: AsyncSession,
    usuario_test: Usuario,
    direccion_test: Direccion,
    categoria_test: Categoria,
):
    await _crear_producto(
        db, usuario_test, direccion_test, categoria_test,
        nombre="Con stock", precio=100.0, sku="SKU-B-13", stock=5,
    )
    await _crear_producto(
        db, usuario_test, direccion_test, categoria_test,
        nombre="Sin stock", precio=100.0, sku="SKU-B-14", stock=0,
    )

    response = await client.get("/busqueda")
    assert response.status_code == 200
    nombres = [item["nombre"] for item in response.json()["items"]]
    assert "Con stock" in nombres
    assert "Sin stock" not in nombres


@pytest.mark.asyncio
async def test_busqueda_pagina_resultados(
    client: AsyncClient,
    db: AsyncSession,
    usuario_test: Usuario,
    direccion_test: Direccion,
    categoria_test: Categoria,
):
    for i in range(5):
        await _crear_producto(
            db, usuario_test, direccion_test, categoria_test,
            nombre=f"Producto P{i}", precio=10.0 + i, sku=f"SKU-PAG-{i}",
        )

    response = await client.get("/busqueda", params={"page": 1, "page_size": 2})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["pages"] == 3


@pytest.mark.asyncio
async def test_busqueda_rechaza_orden_invalido(client: AsyncClient):
    response = await client.get("/busqueda", params={"orden": "campo_inexistente"})
    assert response.status_code == 422
