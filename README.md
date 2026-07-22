# compra-y-venta-monolito

Backend de un sistema de compra y venta con delivery.
Materia: Patrones de Arquitectura de Software.

**Stack:** Python · FastAPI · PostgreSQL · SQLAlchemy 2.x (async) · Alembic · Firebase Authentication · RabbitMQ · nginx

> El repo contiene **dos arquitecturas del mismo sistema**: el monolito modular del TP1
> (`app/`) y su **migración completa a 5 microservicios hexagonales** (`services/`),
> con saga de checkout, database-per-service y API Gateway. El monolito sigue
> funcionando intacto como base de comparación.

---

## Arquitectura de microservicios

```
Cliente ──► API Gateway (nginx :8080) ──► servicios (cada uno con su PostgreSQL)
                 │ bloquea /interno/*
                 ├─ /personas /usuarios /direcciones → Identidad   :8001
                 ├─ /billetera                       → Billetera   :8002  ← PIVOTE de la saga
                 ├─ /productos /busqueda             → Catálogo    :8003
                 ├─ /deliveries                      → Delivery    :8004  ← async vía RabbitMQ
                 └─ /carrito /carrito/checkout       → Carrito     :8005  ← ORQUESTADOR
```

- **Todo hexagonal** (ports & adapters): dominio en `service.py`/`saga.py`, adaptadores REST, de persistencia y de broker.
- **CheckoutSaga** (en Carrito): `ReservarStock → DebitarSaldo (pivote) → DescontarStock → CrearDeliveries (async)`, con compensación (`LiberarStock`), estado persistido, **log de deliverys (outbox + retry)** y comandos **idempotentes por message_id**.
- **RabbitMQ solo para el delivery async**, con un canal de respuesta propio por saga (`carrito.respuesta.<saga_id>`).

Detalle completo: [`SPECS_MICROSERVICIOS.md`](SPECS_MICROSERVICIOS.md) · [`PLAN_MIGRACION_MICROSERVICIOS.md`](PLAN_MIGRACION_MICROSERVICIOS.md) · diagramas en [`docs/diagramas/`](docs/diagramas/README.md).

### Levantar los microservicios

```bash
# Requiere ./firebase-service-account.json (credenciales reales de Firebase)
docker compose --profile microservices up -d --build

curl localhost:8080/health        # gateway
curl localhost:8080/productos     # catálogo (público)
# El resto de los endpoints requieren Authorization: Bearer <firebase_id_token>
```

Colección Postman de los microservicios: [`docs/postman_microservicios.json`](docs/postman_microservicios.json) (variable `base_url` ya apunta al gateway).

### Tests de los microservicios

```bash
docker compose up -d test-db identidad-test-db billetera-test-db catalogo-test-db delivery-test-db carrito-test-db
cd services/<servicio> && pytest tests/ -v     # o correr los 6 (monolito incluido)
```

CI: `.github/workflows/ci.yml` corre el monolito + los 5 servicios (matrix) en cada push.

---

# El monolito (TP1)

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

## Documentación

| Recurso | Ubicación |
|---------|-----------|
| Swagger / OpenAPI | `http://localhost:8000/docs` (servidor corriendo) |
| Colección Postman | [`docs/postman_collection.json`](docs/postman_collection.json) |
| Diagramas C4 y UML | [`docs/diagramas/`](docs/diagramas/README.md) |

### Colección Postman

Importar el archivo `docs/postman_collection.json` en Postman. Incluye carpetas para cada módulo:

- `00 - Auth` — obtención del token Firebase
- `01 - Personas` / `02 - Usuarios` / `03 - Direcciones`
- `04 - Productos` / `05 - Búsqueda`
- `06 - Billetera` / `07 - Carrito` / `08 - Delivery`

Configurar la variable de entorno `base_url` con `http://localhost:8000` y `token` con el ID token de Firebase.

### Diagramas

Están en `docs/diagramas/` como archivos Markdown con diagramas Mermaid:

- **C4:** Contexto, Contenedores, Componentes
- **UML:** Modelo de datos, Secuencia de compra, Secuencia de entrega

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
