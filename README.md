# compra-y-venta-monolito

Backend de un sistema de compra y venta con arquitectura monolítica.
Materia: Patrones de Arquitectura de Software.

**Stack:** Python · FastAPI · PostgreSQL · SQLAlchemy 2.x (async) · Alembic · Firebase Authentication

---

## Requisitos previos

- Python 3.9+
- PostgreSQL corriendo (local o Docker)
- Cuenta de Firebase con un proyecto configurado y el archivo `firebase-service-account.json` descargado

---

## Setup

```bash
# 1. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con los datos de tu BD y Firebase

# 4. Colocar el archivo de credenciales de Firebase
# Descargar desde Firebase Console → Configuración del proyecto → Cuentas de servicio
cp firebase-service-account.json ./firebase-service-account.json

# 5. Correr migraciones
alembic upgrade head

# 6. Levantar el servidor
uvicorn app.main:app --reload
```

Documentación interactiva disponible en `http://localhost:8000/docs`.

---

## Variables de entorno (.env)

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/compra_venta
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.json
FIREBASE_WEB_API_KEY=
FIREBASE_AUTH_DOMAIN=

# Billetera virtual
BILLETERA_LIMITE_CARGA=100000
BILLETERA_MONEDA=ARS
```

---

## Autenticación

La autenticación está delegada completamente a **Firebase Authentication**. El backend no gestiona contraseñas ni emite tokens propios.

Cada request a un endpoint protegido debe incluir el header:
```
Authorization: Bearer <firebase_id_token>
```

El token se obtiene desde el cliente autenticándose contra Firebase (email/password, Google, etc.).

---

## Estructura

```
app/
├── core/               # Config, base de datos, Firebase, dependencias
└── modules/
    ├── admin/          # ABM de Personas, Usuarios y Direcciones
    ├── productos/      # Catálogo de productos y categorías
    ├── busqueda/       # Búsqueda y filtrado de productos
    ├── carrito/        # Carrito de compras y checkout
    ├── billetera/      # Billetera virtual y transacciones
    ├── delivery/       # Gestión de entregas (DeliveryOrders)
    └── notificaciones/ # Notificaciones internas
alembic/                # Migraciones de base de datos
tests/                  # Tests de integración
```

---

## Endpoints principales

| Módulo | Método | Ruta |
|--------|--------|------|
| Personas | GET / POST | `/personas` |
| Personas | GET / PUT / DELETE | `/personas/{id}` |
| Usuarios | POST | `/personas/{id}/usuarios` |
| Usuarios | PUT / DELETE | `/usuarios/{id}` |
| Direcciones | GET / POST | `/personas/{id}/direcciones` |
| Direcciones | PUT / DELETE | `/direcciones/{id}` |
| Productos | GET / POST | `/productos` |
| Productos | GET / PUT / DELETE | `/productos/{id}` |
| Búsqueda | GET | `/busqueda` |
| Billetera | GET | `/billetera` |
| Billetera | POST | `/billetera/cargar` |
| Billetera | GET | `/billetera/historial` |
| Carrito | GET / DELETE | `/carrito` |
| Carrito | POST | `/carrito/items` |
| Carrito | PUT / DELETE | `/carrito/items/{producto_id}` |
| Carrito | POST | `/carrito/checkout` |
| Delivery | GET | `/deliveries` |
| Delivery | GET | `/deliveries/mis-asignados` |
| Delivery | GET | `/deliveries/{id}` |
| Delivery | POST | `/deliveries/{id}/tomar` |
| Delivery | POST | `/deliveries/{id}/entregar` |

La documentación completa con schemas y ejemplos está en `/docs` (Swagger).

---

## Tests

Requiere una base de datos PostgreSQL de test configurada en `tests/conftest.py`.

```bash
pytest tests/ -v
```
