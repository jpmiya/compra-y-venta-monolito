# compra-y-venta-monolito

Backend de un sistema de compra y venta con arquitectura monolítica.
Materia: Patrones de Arquitectura de Software.

**Stack:** Python · FastAPI · PostgreSQL · SQLAlchemy (async) · Alembic · JWT

---

## Setup

```bash
# 1. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
copy .env.example .env
# Editar .env con los datos de tu BD

# 4. Correr migraciones
alembic upgrade head

# 5. Levantar el servidor
uvicorn app.main:app --reload
```

Documentación interactiva disponible en `http://localhost:8000/docs`.

## Estructura

```
app/
├── core/           # Config, DB, seguridad, dependencias
└── modules/
    ├── auth/       # Autenticación y usuarios (JWT)
    ├── productos/  # Catálogo, categorías, reseñas
    ├── carrito/    # Carrito de compras
    ├── ordenes/    # Órdenes y checkout
    ├── busqueda/   # Búsqueda y filtrado avanzado
    └── notificaciones/  # Notificaciones por email
alembic/            # Migraciones de base de datos
tests/              # Tests unitarios e integración
```

## Tests

```bash
pytest
```
