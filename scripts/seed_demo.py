"""
Script de seed para datos de demostración.
Crea una persona, usuario, direcciones, productos y billetera con saldo.
Uso: python scripts/seed_demo.py
"""
import asyncio
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.modules.admin.models import Persona, Usuario, Direccion
from app.modules.productos.models import Producto, Categoria
from app.modules.billetera.models import BilleteraVirtual

FIREBASE_UID = os.getenv("SEED_FIREBASE_UID", "FKXmWKkir1MPyeu6uve2ZTfjCwO2")
EMAIL       = os.getenv("SEED_EMAIL", "juan@test.com")


async def seed():
    async with AsyncSessionLocal() as db:
        # --- Usuario / Persona ---
        result = await db.execute(select(Usuario).where(Usuario.firebase_uid == FIREBASE_UID))
        usuario = result.scalar_one_or_none()

        if usuario:
            print(f"Usuario {EMAIL} ya existe, usando el existente.")
            persona_id = usuario.persona_id
        else:
            persona = Persona(
                nombre_completo="Juan Demo",
                documento_identidad="12345678",
                telefono="1134567890",
                estado="activo",
            )
            db.add(persona)
            await db.flush()

            usuario = Usuario(
                persona_id=persona.id,
                email=EMAIL,
                firebase_uid=FIREBASE_UID,
                estado="activo",
            )
            db.add(usuario)
            await db.flush()
            persona_id = persona.id
            print(f"Persona + Usuario creados: {EMAIL}")

        # --- Direcciones ---
        result = await db.execute(select(Direccion).where(Direccion.persona_id == persona_id))
        direcciones = result.scalars().all()

        if not direcciones:
            dir1 = Direccion(persona_id=persona_id, calle="Av. Corrientes", numero="1234",
                             ciudad="Buenos Aires", provincia="CABA",
                             descripcion="Local comercial", activa=True)
            dir2 = Direccion(persona_id=persona_id, calle="Av. Rivadavia", numero="5678",
                             ciudad="Buenos Aires", provincia="CABA",
                             descripcion="Depósito", activa=True)
            db.add_all([dir1, dir2])
            await db.flush()
            direcciones = [dir1, dir2]
            print("Direcciones creadas.")
        else:
            print(f"Ya hay {len(direcciones)} direcciones, saltando.")

        # --- Categorías ---
        result = await db.execute(select(Categoria))
        cats = {c.nombre: c for c in result.scalars().all()}
        if not cats:
            print("No hay categorías. Corré primero: alembic upgrade head")
            await db.rollback()
            return

        # --- Productos ---
        result = await db.execute(select(Producto).where(Producto.vendedor_id == usuario.id))
        if not result.scalars().first():
            dir_venta = direcciones[0]
            cat_elec = cats.get("Electrónica") or list(cats.values())[0]
            cat_ropa = cats.get("Ropa y Calzado") or list(cats.values())[0]

            productos = [
                Producto(nombre="Notebook Lenovo IdeaPad",
                         descripcion='Notebook 15", 16GB RAM, SSD 512GB, Intel i5',
                         precio=250000, stock=5, sku="NB-LENOVO-001",
                         vendedor_id=usuario.id, direccion_punto_venta_id=dir_venta.id,
                         categoria_id=cat_elec.id, activo=True, imagenes=[]),
                Producto(nombre="Mouse Logitech MX Master",
                         descripcion="Mouse inalámbrico ergonómico, 4000 DPI",
                         precio=15000, stock=20, sku="MS-LOGI-001",
                         vendedor_id=usuario.id, direccion_punto_venta_id=dir_venta.id,
                         categoria_id=cat_elec.id, activo=True, imagenes=[]),
                Producto(nombre="Teclado Mecánico RGB",
                         descripcion="Teclado mecánico con switches Cherry MX Red",
                         precio=18000, stock=10, sku="TK-MECH-001",
                         vendedor_id=usuario.id, direccion_punto_venta_id=dir_venta.id,
                         categoria_id=cat_elec.id, activo=True, imagenes=[]),
                Producto(nombre="Zapatillas Nike Air Max",
                         descripcion="Zapatillas deportivas talle 42, color blanco",
                         precio=45000, stock=3, sku="ZP-NIKE-001",
                         vendedor_id=usuario.id, direccion_punto_venta_id=dir_venta.id,
                         categoria_id=cat_ropa.id, activo=True, imagenes=[]),
            ]
            db.add_all(productos)
            print("Productos creados.")
        else:
            print("Ya hay productos, saltando.")

        # --- Billetera ---
        result = await db.execute(select(BilleteraVirtual).where(BilleteraVirtual.usuario_id == usuario.id))
        billetera = result.scalar_one_or_none()
        if not billetera:
            db.add(BilleteraVirtual(usuario_id=usuario.id, saldo=100000.0, moneda="ARS"))
            print("Billetera creada con $100.000 ARS.")
        else:
            print(f"Billetera ya existe con saldo ${billetera.saldo}.")

        await db.commit()
        print("\nSeed completado.")


if __name__ == "__main__":
    asyncio.run(seed())
