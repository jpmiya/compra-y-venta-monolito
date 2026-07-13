# CONTEXT — compra-y-venta-monolito

> Documento de contexto para retomar el repo rápido. Fuente de verdad del **estado funcional**: `SPECS.md` (sección "Estado Actual" + enunciado completo). Este archivo resume lo esencial para arrancar sin releer todo.

---

## Qué es

Backend monolítico de un sistema de **compra y venta de productos** con delivery. TP académico de *Patrones de Arquitectura de Software*. Estado: **TP1 completo** (última iteración 2026-04-30). 27/27 tests pasando en el último push registrado.

Desarrollado por **dos personas, cada una con su agente Claude** (Juampi y Nicolas). Convención de colaboración: antes de cada `git push`, el agente actualiza la sección "Estado Actual" de `SPECS.md`. Al retomar, leer esa sección primero.

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.11+ (compatible 3.9) · FastAPI |
| Base de datos | PostgreSQL 15 |
| ORM | SQLAlchemy 2.x async (asyncpg) |
| Migraciones | Alembic |
| Auth | **Firebase Authentication** (Admin SDK) — sin JWT propio, sin contraseñas locales |
| Validación | Pydantic v2 |
| Testing | Pytest + pytest-asyncio + httpx |
| UI web | Jinja2 + Bootstrap 5 (server-side render) |
| Contenedor | Docker + docker-compose |
| CI | GitHub Actions (`.github/workflows/ci.yml`) |

---

## Estructura real del repo

```
app/
├── core/
│   ├── config.py          # pydantic-settings (.env)
│   ├── database.py        # async engine
│   ├── dependencies.py    # get_db, get_current_user (guards)
│   ├── firebase.py        # init Admin SDK + verify_id_token
│   └── encryption.py      # AES-256-GCM EncryptedString (TypeDecorator)
├── main.py                # registra routers (orden: admin antes que web)
├── modules/
│   ├── admin/             # ABM Personas, Usuarios, Direcciones  (¡este es el "auth"!)
│   ├── productos/         # catálogo + categorías
│   ├── busqueda/          # búsqueda/filtrado (solo router; usa productos)
│   ├── carrito/           # carrito + checkout (transacción atómica)
│   ├── billetera/         # billetera virtual + transacciones
│   ├── delivery/          # DeliveryOrders (pendiente→asignada→entregada)
│   ├── notificaciones/    # notificaciones internas (models + service)
│   └── ordenes/           # ⚠️ NO es parte del TP — genera tablas extra (deuda)
└── web/router.py          # UI Jinja2, todas las rutas bajo prefijo /ui/
templates/                 # vistas Jinja2 + Bootstrap
alembic/versions/          # b946...initial_schema · c1a2...seed_categorias
tests/unit/                # admin, productos, busqueda, carrito, checkout, billetera, delivery
scripts/                   # utilidades
docs/
├── postman_collection.json
└── diagramas/             # C4 (contexto/contenedores/componentes) + UML (datos/compra/entrega), Mermaid
```

Patrón por módulo: `models.py` / `schemas.py` / `service.py` / `router.py`. **Lógica de negocio en el service, no en el router.**

---

## Modelo de datos (completo — extraído del código real)

> ⚠️ Para diagramas, usar **estas tablas**, no las de SPECS.md §4. El código real difiere del enunciado: `categoria` es una entidad propia (no un string), existe `Resena`, `Producto` tiene `sku`/`imagenes[]`/`calificacion_promedio` (no `imagen`), el campo es `vendedor_id` (no `usuario_vendedor_id`), `Carrito` tiene `codigo_descuento`/`descuento`, `Notificacion` tiene su propio set de campos, y `Rol` es many-to-many vía tabla `usuario_roles`.

Todos los PK son `UUID` (`as_uuid=True`, default `uuid4`). Todos los `DateTime` son `timezone=True`. Bajas **lógicas** (soft delete) vía `estado`/`activo`/`activa`.

### Persona (`personas`)
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| nombre_completo | String(200) | NOT NULL |
| documento_identidad | EncryptedString(255) | **único**, indexado, cifrado AES-GCM |
| telefono | String(20) | nullable |
| fecha_nacimiento | Date | nullable |
| fecha_registro | DateTime | default utcnow |
| estado | Enum(`activo`,`inactivo`) | default `activo` |

### Usuario (`usuarios`)
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| persona_id | UUID | FK → personas, NOT NULL |
| email | EncryptedString(500) | **único**, indexado, cifrado |
| firebase_uid | String(128) | **único**, indexado |
| fecha_ultimo_acceso | DateTime | nullable |
| estado | Enum(`activo`,`inactivo`) | default `activo` |

### Rol (`roles`) — M:N con Usuario vía tabla `usuario_roles`
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| nombre | String(50) | único |

`usuario_roles`: (`usuario_id` FK→usuarios, `rol_id` FK→roles) — PK compuesta.

### Direccion (`direcciones`)
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| persona_id | UUID | FK → personas, NOT NULL |
| calle / numero / ciudad / provincia | String | NOT NULL |
| descripcion | String(200) | nullable |
| activa | Boolean | default True (soft delete) |

### Categoria (`categorias`)
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| nombre | String(100) | único |
| descripcion | Text | nullable |
| imagen | String(500) | nullable |

### Producto (`productos`)
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| nombre | String(255) | NOT NULL, indexado |
| descripcion | Text | nullable |
| precio | Float | NOT NULL |
| categoria_id | UUID | FK → categorias, NOT NULL, indexado |
| stock | Integer | default 0 |
| sku | String(100) | **único**, indexado |
| imagenes | ARRAY(String) | default [] |
| vendedor_id | UUID | FK → usuarios, NOT NULL |
| direccion_punto_venta_id | UUID | FK → direcciones, NOT NULL |
| activo | Boolean | default True (soft delete) |
| calificacion_promedio | Float | default 0.0 |
| fecha_creacion | DateTime | default utcnow |

### Resena (`resenas`)
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| producto_id | UUID | FK → productos, NOT NULL, indexado |
| usuario_id | UUID | FK → usuarios, NOT NULL |
| calificacion | Integer | NOT NULL |
| comentario | Text | nullable |
| fecha_creacion | DateTime | default utcnow |

### Carrito (`carritos`)
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| usuario_id | UUID | FK → usuarios, **único** (1 por usuario) |
| codigo_descuento | String(50) | nullable |
| descuento | Float | default 0.0 |
| fecha_creacion | DateTime | persistente, sin vencimiento |

### CarritoItem (`carrito_items`) — UNIQUE(carrito_id, producto_id)
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| carrito_id | UUID | FK → carritos, NOT NULL (cascade delete-orphan) |
| producto_id | UUID | FK → productos, NOT NULL |
| cantidad | Integer | NOT NULL |
| precio_unitario | Float | precio al momento de agregar |

### BilleteraVirtual (`billeteras`)
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| usuario_id | UUID | FK → usuarios, **único** (1 por usuario) |
| saldo | Float | default 0.0 |
| moneda | String(10) | default ARS |

### TransaccionBilletera (`transacciones_billetera`)
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| billetera_id | UUID | FK → billeteras, NOT NULL (cascade delete-orphan) |
| tipo | Enum(`carga`,`compra`) | NOT NULL |
| monto | Float | NOT NULL |
| descripcion | String(255) | NOT NULL |
| fecha | DateTime | default utcnow |

### DeliveryOrder (`delivery_orders`) — se crea **uno por ítem** en el checkout
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| comprador_id | UUID | FK → usuarios, NOT NULL |
| producto_id | UUID | FK → productos, NOT NULL |
| cantidad | Integer | NOT NULL |
| precio_unitario | Float | NOT NULL |
| direccion_entrega | String(500) | NOT NULL (texto, dirección del comprador) |
| direccion_punto_venta_id | UUID | FK → direcciones, NOT NULL |
| entregador_id | UUID | FK → usuarios, **nullable** |
| estado | Enum(`pendiente`,`asignada`,`entregada`) | default `pendiente` |
| fecha_creacion | DateTime | default utcnow |
| fecha_asignacion | DateTime | nullable |
| fecha_entrega | DateTime | nullable |

### Notificacion (`notificaciones`)
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| usuario_id | UUID | NOT NULL, indexado (**sin FK declarada**) |
| tipo | Enum(`orden_creada`,`orden_actualizada`,`password_reset`,`bienvenida`) | NOT NULL |
| asunto | String(255) | NOT NULL |
| cuerpo | Text | NOT NULL |
| enviada | Boolean | default False |
| intentos | Integer | default 0 |
| fecha_creacion | DateTime | default utcnow |
| fecha_envio | DateTime | nullable |

### ⚠️ Orden / OrdenItem (`ordenes` / `orden_items`) — EXCLUIR de los diagramas del TP
Módulo `ordenes` que **no es parte del TP1** (deuda técnica). Existe en BD pero **no debe aparecer** en los diagramas del enunciado. `Orden` (numero_orden único, subtotal/impuesto/descuento/total, estado de 6 valores, FK usuario) 1—N `OrdenItem` (FK orden, FK producto, snapshot nombre/precio).

### Relaciones (cardinalidades)
```
Persona 1 ──< N Usuario          Persona 1 ──< N Direccion
Usuario N >──< N Rol  (usuario_roles)
Categoria 1 ──< N Producto
Usuario (vendedor) 1 ──< N Producto
Direccion 1 ──< N Producto  (punto de venta)
Producto 1 ──< N Resena          Usuario 1 ──< N Resena
Usuario 1 ──1 Carrito  (único)   Carrito 1 ──< N CarritoItem
Producto 1 ──< N CarritoItem
Usuario 1 ──1 BilleteraVirtual (único)
BilleteraVirtual 1 ──< N TransaccionBilletera
Usuario (comprador) 1 ──< N DeliveryOrder
Usuario (entregador, opcional) 1 ──< N DeliveryOrder
Producto 1 ──< N DeliveryOrder   Direccion 1 ──< N DeliveryOrder
Usuario 1 ──< N Notificacion  (lógica, sin FK física)
```

---

## Decisiones técnicas clave (no obvias desde el código)

- **Auth 100% Firebase.** Cada request protegido valida `Authorization: Bearer <firebase_id_token>` con `verify_id_token()`. No hay contraseñas en la BD.
- **Auto-registro:** si el token Firebase es válido pero el usuario no existe en BD local, se lo redirige a `/web/registro` para completar datos. Primer acceso sin intervención manual.
- **Rutas web bajo `/ui/`** para no colisionar con el `admin_router` (que registra `GET /personas` con Bearer). El orden de registro importa: admin antes que web.
- **Checkout atómico** (un solo `db.commit()`): valida carrito no vacío → valida stock por ítem → verifica saldo → crea un `DeliveryOrder` por ítem → descuenta stock → descuenta saldo (`descontar_saldo` sin commit propio) → vacía carrito. Usa `CarritoItem.precio_unitario` (precio al agregar), no el precio actual.
- **Encriptación determinística** AES-256-GCM (nonce = SHA-256(key+plaintext)[:12]) en `documento_identidad` y `email`, para permitir búsquedas SQL por igualdad. Si `ENCRYPTION_KEY` está vacía, funciona sin cifrado (solo dev).
- **Búsqueda** filtra `stock > 0` y devuelve `direccion_punto_venta` completa vía `selectinload`.
- **`LoggingMiddleware` ASGI puro** (no `BaseHTTPMiddleware`) — evita conflictos de event loop con asyncpg en tests.
- **Tests:** engine creado dentro del fixture, sesión DB fresca por request, mock de Firebase en `app.core.dependencies`. `setup_db` sincrónico con `asyncio.new_event_loop()` para evitar conflictos de event loop en pytest-asyncio.
- **Rutas con segmento fijo antes que dinámico:** p.ej. `GET /deliveries/mis-asignados` se declara antes de `GET /deliveries/{id}` para que FastAPI no parsee el string como UUID.

---

## Entorno local (último setup conocido)

- PostgreSQL en **Docker, puerto 5433** (5432 ocupado por un Postgres local). User `postgres`, DB `compra_venta_db`. (SPECS menciona pass `pass123` en la última iteración; iteraciones previas usaban `postgres`.)
- BD de test separada: `compra_venta_test`.
- `firebase-service-account.json` en la raíz (en `.gitignore`, **no se commitea** — pero el archivo existe localmente).

```bash
# BD
docker run -d --name postgres-compraventa -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=compra_venta_db -p 5433:5432 postgres:15
alembic upgrade head
pytest tests/ -v
uvicorn app.main:app --reload   # docs en http://localhost:8000/docs ; UI en /ui/
```

`ENCRYPTION_KEY` se genera con:
`python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`

---

## Deuda técnica / cosas a saber

- Módulo **`ordenes`** existe pero **no es parte del TP**; genera tablas extra en la migración. Se puede eliminar.
- Python 3.9 está EOL (google-auth tira `FutureWarning` en tests). No afecta funcionalidad; conviene 3.11+.
- Sin `ENCRYPTION_KEY` los datos sensibles quedan en texto plano (funciona, pero inseguro).
- Commits recientes posteriores al "TP completo": fix lazy-load de `direccion_punto_venta` y refresh de `carrito.items`; tests de busqueda/productos/carrito.

---

## Cómo trabaja el usuario (preferencias)

- Compilar y correr tests después de cada cambio.
- Explicación breve al final de cada implementación (para poder explicar "¿cómo lo hiciste?").
- Ante decisiones arquitectónicas: presentar las 3 mejores opciones y dejar elegir.
- Tests por comportamiento esperado, no tautológicos. venv siempre. Secretos en `.env`.
