# SPECS - Sistema de Compra y Venta de Productos

**Fuente**: Enunciado oficial TP1 - Monolito
**Versión**: 2.0 (reescrito desde el PDF del enunciado)

---

## 🤝 Metodología de Colaboración Entre Agentes

Este proyecto es desarrollado por dos personas, cada una con su propio agente Claude. Para mantener la continuidad entre sesiones y entre agentes, se sigue esta convención:

### Regla principal
**Antes de cada `git push`, el agente activo debe actualizar la sección "Estado Actual" de este archivo** con un resumen de lo implementado, lo que falta, y cualquier decisión técnica relevante que el otro agente necesite saber.

### Qué documentar antes de cada push
1. **Qué se implementó** en esta sesión (módulos, endpoints, modelos).
2. **Estado de los tests** — si corren, si hay alguno roto, coverage estimado.
3. **Decisiones técnicas tomadas** que no son obvias desde el código.
4. **Próximos pasos sugeridos** para quien continúe.
5. **Problemas conocidos o deuda técnica** que quedó pendiente.

### Cómo leer este archivo (para el agente que retoma)
Al iniciar una sesión nueva, leer primero la sección "Estado Actual" de este archivo antes de explorar el código. Esa sección es la fuente de verdad del estado del proyecto en el último push.

### Responsabilidad del agente
- El agente que recibe la instrucción de push es quien actualiza "Estado Actual".
- El desarrollador avisa al agente: *"voy a pushear"* y el agente actualiza antes de confirmar el push.
- Si el agente retomante encuentra que "Estado Actual" está desactualizado, debe actualizarlo al terminar su sesión.

---

## 📍 Estado Actual

### Sesión 2026-04-28 — Iteración 7 (Nicolas)

**Qué se hizo en esta sesión:**
- Parámetros de configuración completos en `config.py` y `.env.example`: `SEGURIDAD_MAX_INTENTOS_LOGIN`, `SEGURIDAD_TIEMPO_SESION_MINUTOS`, `BUSQUEDA_MAX_RESULTADOS`, `NOTIFICACIONES_EMAIL_HABILITADO`, `NOTIFICACIONES_EMAIL_REMITENTE`, `FIREBASE_PROJECT_ID`.
- README.md actualizado: stack correcto (Firebase en lugar de JWT), sección de autenticación, tabla completa de endpoints, instrucciones de configuración.
- Fix búsqueda: filtro `stock > 0` agregado — solo devuelve productos con stock disponible.
- Fix búsqueda: `ProductoResponse` ahora incluye `direccion_punto_venta` con datos completos (calle, ciudad, etc.) usando `selectinload`.
- Migración Alembic inicial generada y aplicada (`alembic/versions/b946013361d1_initial_schema.py`). BD levantada con Docker en puerto 5433 (`postgres:15`, user: `postgres`, pass: `postgres`, DB: `compra_venta_db`).
- Fix compatibilidad Python 3.9: reemplazado `X | None` por `Optional[X]` en todos los modelos y services.
- Fix `alembic/env.py`: agregados imports de módulos `billetera` y `delivery`.
- `BaseHTTPMiddleware` reemplazado por `LoggingMiddleware` puro (ASGI directo) — evitaba conflictos de event loop con asyncpg en tests.
- Tests 27/27 pasando. Fixes al conftest: engine creado dentro del fixture (no a nivel módulo), sesión fresca por request en el cliente de test, mock de Firebase corregido (`app.core.dependencies` en lugar de `app.core.firebase`), orden de routers corregido (admin antes que web).

**Estado de los tests:** 27/27 pasando ✅

**Decisiones técnicas:**
- Docker en puerto 5433 para la BD de test (puerto 5432 ocupado por PostgreSQL 18 instalado localmente).
- Cada request en los tests recibe su propia sesión DB (igual que en producción) para evitar problemas de caché del identity map de SQLAlchemy.
- `setup_db` es sincrónico (usa `asyncio.new_event_loop()`) para evitar conflictos de event loop entre fixtures de sesión y de función en pytest-asyncio.

**Próximos pasos sugeridos:**

1. **Dockerfile** — crear `Dockerfile` en la raíz del proyecto para empaquetar la app. El enunciado pide que la imagen esté en GitLab. Usar imagen base `python:3.11-slim`, copiar el código, instalar dependencias, exponer puerto 8000, comando: `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

2. **Pipeline CI/CD** — crear `.gitlab-ci.yml` (o `.github/workflows/ci.yml` si se usa GitHub). Debe correr los tests automáticamente en cada push. Para los tests necesita un PostgreSQL de servicio en el pipeline.

3. **Colección Postman** — crear y exportar una colección Postman con todos los endpoints del sistema. Incluir autenticación via Firebase ID Token en el header `Authorization: Bearer <token>`. El enunciado la pide explícitamente en la sección 6.3.

4. **Diagramas C4 y UML** — el enunciado pide diagrama de contexto, contenedores y componentes incluyendo Firebase. Guardarlos en un directorio `/docs/diagramas/` en el repo y referenciarlos desde el README.

5. **Levantar la BD y correr migraciones** — si Juampi levanta en su entorno, los comandos son:
   ```bash
   # Con Docker:
   docker run -d --name postgres-compraventa -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=compra_venta_db -p 5433:5432 postgres:15
   # Migrar:
   alembic upgrade head
   # Correr tests:
   pytest tests/ -v
   ```
   La BD de test también necesita existir: `CREATE DATABASE compra_venta_test;`

**Problemas conocidos / deuda técnica:**
- El módulo `ordenes` (Orden, OrdenItem) existe en el repo pero no es parte del TP — genera tablas extras en la migración. Se puede eliminar si molesta.
- Python 3.9 llegó a fin de vida (google-auth lanza FutureWarning en los tests). Conviene migrar a Python 3.11+ cuando haya tiempo.
- El `ENCRYPTION_KEY` en `.env` debe generarse con: `python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`. Sin esa variable los datos sensibles se guardan en texto plano (funciona pero no es seguro).

---

### Sesión 2026-04-26 — Iteración 6 (Nicolas)

**Qué se hizo en esta sesión:**
- Implementada encriptación AES-256-GCM en `app/core/encryption.py` con `EncryptedString` TypeDecorator.
- Aplicada a `documento_identidad` (Persona) y `email` (Usuario) — se cifran automáticamente al guardar y descifran al leer.
- Agregada variable `ENCRYPTION_KEY` en `config.py` (base64 de 32 bytes).
- Agregado middleware de logging HTTP en `main.py`: registra método, path, status y duración de cada request.
- Agregados logs de operaciones críticas: CHECKOUT, DELIVERY TOMADO, DELIVERY ENTREGADO.
- README.md actualizado (stack correcto, sección Firebase, tabla de endpoints, variables de entorno).
- Fix: búsqueda ahora filtra `stock > 0`.
- Fix: `ProductoResponse` incluye datos completos de `direccion_punto_venta` (calle, ciudad, etc.).

**Estado de los tests:** Escritos, pendientes de correr contra BD real.

**Decisiones técnicas:**
- Encriptación determinística (nonce = SHA-256(key + plaintext)[:12]) para permitir búsquedas SQL por igualdad sin romper los services existentes.
- Si `ENCRYPTION_KEY` está vacía, el sistema funciona sin cifrado (útil para desarrollo sin configurar la clave).

**Próximos pasos sugeridos:**
1. Juampi: levantar BD, generar `ENCRYPTION_KEY`, correr `alembic upgrade head` + `pytest`.
2. Dockerfile + pipeline CI/CD.
3. Colección Postman.
4. Diagramas C4 y UML.

**Problemas conocidos / deuda técnica:** Ninguno.

---

### Sesión 2026-04-26 — Iteración 5 (Nicolas)

**Qué se hizo en esta sesión:**
- Agregados fixtures `direccion_test`, `categoria_test` y `producto_test` en `conftest.py`.
- Creado `tests/unit/test_billetera.py` — 6 tests: creación automática, carga, acumulación, monto negativo, límite superado, historial.
- Creado `tests/unit/test_checkout.py` — 7 tests: carrito vacío, sin saldo, checkout exitoso, descuento de saldo, vaciado de carrito, descuento de stock, transacción en historial.
- Creado `tests/unit/test_delivery.py` — 7 tests: listar pendientes, detalle, tomar, tomar ya asignado, mis-asignados, entregar, entregar sin tomar.

**Estado de los tests:** Escritos, pendientes de correr contra BD real (Juampi configura el entorno).

**Decisiones técnicas:**
- Los tests de delivery usan un helper `_hacer_checkout()` para crear deliveries sin repetir código.
- Todos los tests verifican comportamiento esperado (status codes + valores de negocio), no implementación interna.

**Próximos pasos sugeridos:**
1. Juampi: levantar BD y correr `alembic upgrade head` + `pytest`.
2. Revisar si hay casos de borde faltantes una vez que corran los tests.

**Problemas conocidos / deuda técnica:** Ninguno.

---

### Sesión 2026-04-26 — Iteración 4 (Nicolas)

**Qué se hizo en esta sesión:**
- Agregado `POST /carrito/checkout` con transacción atómica.
- Agregados schemas `CheckoutRequest` (requiere `direccion_entrega`) y `CheckoutResponse` (lista de delivery orders + total cobrado + moneda).
- La función `checkout()` en el service ejecuta en un único `db.commit()`:
  1. Valida que el carrito no esté vacío.
  2. Valida stock activo por cada item.
  3. Verifica saldo suficiente en billetera.
  4. Crea un `DeliveryOrder` por cada item.
  5. Descuenta stock de cada producto.
  6. Descuenta saldo de la billetera (vía `descontar_saldo` sin commit propio).
  7. Vacía el carrito (elimina items, resetea descuento).
- Router actualizado con el nuevo endpoint.

**Estado de los tests:** Sin tests aún.

**Decisiones técnicas:**
- El import de `billetera.service` dentro de la función evita importaciones circulares entre módulos.
- El checkout usa el precio guardado en `CarritoItem.precio_unitario` (precio al momento de agregar), no el precio actual del producto — comportamiento estándar de e-commerce.

**Próximos pasos sugeridos:**
1. Correr primera migración Alembic.
2. Escribir tests.

**Problemas conocidos / deuda técnica:** Ninguno.

---

### Sesión 2026-04-26 — Iteración 3 (Nicolas)

**Qué se hizo en esta sesión:**
- Creado módulo `delivery` completo: modelos, schemas, service, router.
- `DeliveryOrder`: estados `pendiente → asignada → entregada`, registra fecha de asignación y entrega automáticamente.
- Endpoints: `GET /deliveries`, `GET /deliveries/mis-asignados`, `GET /deliveries/{id}`, `POST /deliveries/{id}/tomar`, `POST /deliveries/{id}/entregar`.
- Router registrado en `main.py`.

**Estado de los tests:** Sin tests aún.

**Decisiones técnicas:**
- `GET /deliveries/mis-asignados` se declara antes de `GET /deliveries/{id}` para evitar que FastAPI intente parsear el string como UUID.
- Las validaciones de estado y pertenencia del entregador viven en el service.
- `DeliveryOrder` no tiene relaciones ORM explícitas para mantener el modelo liviano; las FKs alcanzan para las migraciones.

**Próximos pasos sugeridos:**
1. Agregar `POST /carrito/checkout` con transacción atómica.
2. Correr primera migración Alembic.
3. Escribir tests.

**Problemas conocidos / deuda técnica:** Ninguno.

---

### Sesión 2026-04-26 — Iteración 2 (Nicolas)

**Qué se hizo en esta sesión:**
- Creado módulo `billetera` completo: modelos, schemas, service, router.
- `BilleteraVirtual`: un usuario tiene una única billetera (unique en usuario_id). Se crea automáticamente al primer acceso.
- `TransaccionBilletera`: enum `carga / compra`. Se registra en cada operación.
- Endpoints: `GET /billetera`, `POST /billetera/cargar`, `GET /billetera/historial`.
- Agregados parámetros `BILLETERA_LIMITE_CARGA` (default 100000) y `BILLETERA_MONEDA` (default ARS) en `config.py`.
- El service expone `descontar_saldo()` para uso interno del checkout (no tiene endpoint propio).
- Router registrado en `main.py`.

**Estado de los tests:** Sin tests aún.

**Decisiones técnicas:**
- `get_or_create_billetera` crea la billetera transparentemente en el primer acceso, sin necesidad de un endpoint de registro explícito.
- `descontar_saldo` no hace commit — delega eso al checkout para que sea parte de la transacción atómica.

**Próximos pasos sugeridos:**
1. Crear módulo `delivery` (DeliveryOrder con flujo pendiente → asignada → entregada).
2. Agregar `POST /carrito/checkout` con transacción atómica.
3. Correr primera migración Alembic.
4. Escribir tests.

**Problemas conocidos / deuda técnica:** Ninguno.

---

### Sesión 2026-04-26 (Nicolas)

**Qué se hizo en esta sesión:**
- Agregado campo `direccion_punto_venta_id` (FK → `direcciones`) en el modelo `Producto`.
- Agregada relación `direccion_punto_venta` en el modelo `Producto`.
- Actualizado `ProductoCreate` para requerir `direccion_punto_venta_id`.
- Actualizado `ProductoUpdate` para permitir actualizar `direccion_punto_venta_id`.
- Actualizado `ProductoResponse` para exponer `direccion_punto_venta_id`.
- Agregada función `validar_direccion_vendedor` en el service: verifica que la dirección exista, esté activa y pertenezca a la persona del vendedor.
- Router de productos actualiza el endpoint `POST /productos` para capturar el `ValueError` de la validación.

**Estado de los tests:** Sin tests aún.

**Decisiones técnicas:**
- Se optó por validar la pertenencia de la dirección comparando `direccion.persona_id == vendedor.persona_id` en el service (no en el router), manteniendo la lógica de negocio centralizada.
- Se mantuvieron los campos extra (SKU, reseñas, imágenes, calificación) ya existentes — Opción B acordada.

**Próximos pasos sugeridos:**
1. Crear módulo `billetera` (BilleteraVirtual + TransaccionBilletera).
2. Crear módulo `delivery` (DeliveryOrder con flujo pendiente → asignada → entregada).
3. Agregar `POST /carrito/checkout` con transacción atómica.
4. Correr primera migración Alembic.
5. Escribir tests.

**Problemas conocidos / deuda técnica:** Ninguno.

---

### Push #1 — 2026-04-26 (Juan)

**Qué se hizo en esta sesión:**
- Migración completa desde Java Spring Boot a Python FastAPI (el código Java fue eliminado).
- Setup del stack: FastAPI, PostgreSQL, SQLAlchemy 2.x async (asyncpg), Alembic, Firebase Admin SDK, Pydantic v2, Pytest + httpx.
- Estructura modular definida: `app/modules/<modulo>/` con `models.py`, `schemas.py`, `service.py`, `router.py` por cada módulo.
- Módulos previstos: `auth`, `productos`, `carrito`, `ordenes`, `busqueda`, `notificaciones`.
- `app/core/` configurado: `config.py` (pydantic-settings), `database.py` (async engine), `security.py` (JWT+bcrypt), `dependencies.py` (get_db, auth guards).
- `alembic/` inicializado; `env.py` preparado para importar todos los modelos.
- `tests/conftest.py` con fixtures async y BD de test separada.
- SPECS.md reescrito desde el PDF del enunciado con modelo de datos completo, endpoints, flujos y checklist.
- `.env.example` creado con todas las variables necesarias (incluyendo Firebase).

**Estado de los tests:** Sin tests implementados aún (solo estructura de conftest).

**Decisiones técnicas:**
- Autenticación 100% delegada a Firebase (no JWT propio). El backend valida el Firebase ID Token en cada request con `firebase_admin.auth.verify_id_token()`.
- Bajas son lógicas (soft delete) salvo excepción explícita.
- Carrito persistente sin vencimiento; un usuario = un carrito.
- Checkout es transacción atómica: valida stock + saldo, genera DeliveryOrders (uno por ítem), descuenta stock y billetera.

**Próximos pasos sugeridos:**
1. Implementar modelos SQLAlchemy: `Persona`, `Usuario`, `Rol`, `Direccion`.
2. Integrar Firebase Admin SDK en `app/core/security.py` y crear el dependency `get_current_user`.
3. Implementar endpoints ABM de Personas, Usuarios y Direcciones (Módulo 5.1).
4. Correr primera migración Alembic.
5. Escribir primeros tests de autenticación y personas.

**Problemas conocidos / deuda técnica:** Ninguno por ahora.

---

## 1. Objetivo

Desarrollar una **aplicación backend** que permita a los usuarios comprar, vender y distribuir productos en línea, garantizando seguridad, rapidez y facilidad de uso.

---

## 2. Alcance de esta etapa

- Un único rol operativo: **administrador** — cualquier usuario autenticado puede realizar todas las acciones.
- La autenticación está delegada completamente a **Firebase Authentication**. El backend no gestiona contraseñas ni emite tokens propios.
- En etapas futuras se dividirán permisos por rol (vendedor, comprador, entregador) y se podría agregar un rol "público" sin autenticación.
- Las bajas son **lógicas** (soft delete) salvo que se indique lo contrario.

---

## 3. Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python + FastAPI |
| Base de datos | PostgreSQL |
| ORM | SQLAlchemy 2.x (async) |
| Migraciones | Alembic |
| Autenticación | Firebase Authentication (Admin SDK) |
| Validación | Pydantic v2 |
| Testing | Pytest + pytest-asyncio + httpx |
| Contenedor | Docker |
| Documentación API | Swagger / OpenAPI (incluido en FastAPI) |

---

## 4. Modelo de Datos Principal

### Persona
Representa a un individuo real. Una Persona puede tener múltiples Usuarios y múltiples Direcciones.

| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| nombre_completo | string | obligatorio |
| documento_identidad | string | único |
| telefono | string | |
| fecha_nacimiento | date | |
| fecha_registro | datetime | auto |
| estado | enum | activo / inactivo |

### Usuario
Representa una cuenta de acceso asociada a una Persona. Las credenciales viven en Firebase.

| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| persona_id | UUID | FK → Persona |
| email | string | único, identificador en Firebase |
| firebase_uid | string | único, UID de Firebase |
| fecha_ultimo_acceso | datetime | |
| estado | enum | activo / inactivo |

### Rol
Un Usuario puede tener uno o más roles: `vendedor`, `comprador`, `entregador`, `administrador`.
En esta etapa todos los usuarios tienen rol administrador implícito.

### Dirección
Una Persona puede tener múltiples direcciones (domicilio, local, depósito). Se usan como punto de venta de productos.

| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| persona_id | UUID | FK → Persona |
| calle | string | |
| numero | string | |
| ciudad | string | |
| provincia | string | |
| descripcion | string | ej: "Local comercial" |
| activa | bool | |

### Producto

| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| nombre | string | obligatorio |
| descripcion | text | obligatorio |
| categoria | string | de catálogo predefinido |
| precio | decimal | positivo |
| stock | int | >= 0 |
| usuario_vendedor_id | UUID | FK → Usuario |
| direccion_punto_venta_id | UUID | FK → Dirección del vendedor |
| activo | bool | soft delete |
| imagen | string | URL, opcional |
| fecha_creacion | datetime | auto |

### Carrito

| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| usuario_id | UUID | FK → Usuario, único |
| fecha_creacion | datetime | persistente, sin vencimiento |

### CarritoItem

| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| carrito_id | UUID | FK → Carrito |
| producto_id | UUID | FK → Producto |
| cantidad | int | > 0 |
| precio_unitario | decimal | precio al momento de agregar |

### BilleteraVirtual

| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| usuario_id | UUID | FK → Usuario, único |
| saldo | decimal | >= 0 |
| moneda | string | configurable |

### TransaccionBilletera

| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| billetera_id | UUID | FK → BilleteraVirtual |
| tipo | enum | carga / compra |
| monto | decimal | |
| descripcion | string | |
| fecha | datetime | auto |

### DeliveryOrder
Se genera **uno por ítem** del carrito al hacer checkout.

| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID | PK |
| comprador_id | UUID | FK → Usuario |
| producto_id | UUID | FK → Producto |
| cantidad | int | |
| precio_unitario | decimal | |
| direccion_entrega | string | dirección del comprador |
| direccion_punto_venta_id | UUID | FK → Dirección del vendedor |
| entregador_id | UUID | FK → Usuario, nullable |
| estado | enum | pendiente / asignada / entregada |
| fecha_creacion | datetime | auto |
| fecha_asignacion | datetime | nullable |
| fecha_entrega | datetime | nullable |

---

## 5. Módulos del Sistema

### 5.1 Módulo de Administración del Sistema

#### ABM de Personas y Usuarios

**Endpoints:**
- `GET /personas` — listar personas
- `POST /personas` — crear persona
- `GET /personas/{id}` — detalle
- `PUT /personas/{id}` — actualizar
- `DELETE /personas/{id}` — baja lógica (estado = inactivo)
- `GET /personas/{id}/usuarios` — usuarios de una persona
- `POST /personas/{id}/usuarios` — asociar nuevo usuario (registra en Firebase y guarda UID)
- `PUT /usuarios/{id}` — actualizar usuario
- `DELETE /usuarios/{id}` — baja lógica

**Validaciones:**
- `documento_identidad` único
- `email` único y válido
- `firebase_uid` único
- No se almacena ni manipula contraseña localmente

#### ABM de Direcciones

- `GET /personas/{id}/direcciones` — listar direcciones de una persona
- `POST /personas/{id}/direcciones` — agregar dirección
- `PUT /direcciones/{id}` — actualizar
- `DELETE /direcciones/{id}` — baja lógica

#### Parámetros de Configuración

Cargados desde `.env`. Deben incluir:
- Conexión a base de datos
- Parámetros de seguridad (intentos de login, tiempo de sesión)
- Billetera virtual (límite de carga, moneda)
- Búsqueda (cantidad máxima de resultados)
- Notificaciones
- Firebase (project ID, API keys, service account)

---

### 5.2 Módulo de Vendedor — Gestión de Productos

**Endpoints:**
- `GET /productos` — listar productos activos (público)
- `GET /productos/{id}` — detalle de producto (público)
- `POST /productos` — crear producto (requiere autenticación)
- `PUT /productos/{id}` — actualizar producto
- `DELETE /productos/{id}` — baja lógica

**Campos obligatorios al crear:**
- Nombre, descripción, categoría, precio, stock
- `usuario_vendedor_id` — se toma del usuario autenticado automáticamente
- `direccion_punto_venta_id` — seleccionada de las direcciones del vendedor

**Validaciones:**
- Precio > 0
- Stock >= 0
- La dirección de punto de venta debe pertenecer al vendedor
- Categoría debe existir en el catálogo predefinido

---

### 5.3 Módulo de Búsqueda

**Endpoints:**
- `GET /busqueda` — búsqueda y listado de productos

**Query params disponibles:**
- `q` — búsqueda por texto libre (aplica sobre nombre y descripción)
- `categoria` — filtrar por categoría
- `orden` — `precio_asc`, `precio_desc`, `nombre`

**Comportamiento:**
- Devuelve solo productos activos con stock > 0
- Muestra: nombre, precio, categoría, imagen, dirección de punto de venta

---

### 5.4 Módulo de Billetera Virtual

**Endpoints:**
- `GET /billetera` — ver saldo actual del usuario autenticado
- `POST /billetera/cargar` — agregar saldo (simulación)
- `GET /billetera/historial` — historial de transacciones (cargas y compras)

**Validaciones:**
- Monto de carga debe ser positivo
- Monto de carga no puede superar el límite configurado en parámetros
- El saldo no puede quedar negativo

---

### 5.5 Módulo de Carrito de Compras

**Endpoints:**
- `GET /carrito` — ver carrito del usuario autenticado
- `POST /carrito/items` — agregar producto
- `PUT /carrito/items/{producto_id}` — modificar cantidad
- `DELETE /carrito/items/{producto_id}` — eliminar item
- `DELETE /carrito` — vaciar carrito
- `POST /carrito/checkout` — procesar compra

**Características:**
- El carrito es persistente (sin fecha de vencimiento)
- Un usuario tiene un único carrito

**Validaciones al agregar/modificar:**
- Producto debe existir y estar activo
- Cantidad > 0
- No superar el stock disponible

#### Proceso de Checkout (`POST /carrito/checkout`)

El sistema debe ejecutar en una sola transacción:
1. Validar stock disponible para cada ítem
2. Verificar que el saldo de la billetera del comprador sea suficiente para el total
3. Generar un `DeliveryOrder` por cada ítem del carrito
4. Vaciar el carrito
5. Descontar el stock de cada producto
6. Descontar el importe total de la billetera del comprador
7. Registrar la transacción en el historial de la billetera

---

### 5.6 Módulo de Delivery / Entregas

**Endpoints:**
- `GET /deliveries` — listar deliveryOrders pendientes (para entregadores)
- `GET /deliveries/{id}` — detalle de un delivery (dirección comprador, producto, cantidad, punto de venta)
- `POST /deliveries/{id}/tomar` — el entregador se asigna como responsable
- `GET /deliveries/mis-asignados` — deliveries asignados al entregador autenticado
- `POST /deliveries/{id}/entregar` — marcar como entregado (registra fecha/hora)

**Estados de un DeliveryOrder:**
```
pendiente → asignada → entregada
```

**Validaciones:**
- Solo se puede tomar un delivery en estado `pendiente`
- Solo el entregador asignado puede marcarlo como `entregado`
- Al marcar entregado se registra la fecha/hora automáticamente

---

## 6. Autenticación — Firebase Authentication

### Cómo funciona
- El **registro y login** son manejados por Firebase del lado del cliente (o vía Postman usando la REST API de Firebase).
- Cada request al backend incluye el **Firebase ID Token** en el header: `Authorization: Bearer <firebase_id_token>`
- El backend usa el **Firebase Admin SDK** (`firebase-admin` para Python) para verificar el token en cada request.
- Una vez verificado, se extrae el `firebase_uid` y se busca el Usuario correspondiente en la BD local.
- **No se almacenan contraseñas en la base de datos local.**
- Firebase gestiona recuperación de contraseñas y verificación de email.

### Flujo de verificación en el backend
```
Request con Bearer Token
  ↓
Middleware verifica token con firebase_admin.auth.verify_id_token()
  ↓
Extrae firebase_uid del payload
  ↓
Busca Usuario en BD por firebase_uid
  ↓
Inyecta usuario en el contexto del endpoint
```

### Configuración requerida en .env
```
FIREBASE_PROJECT_ID=...
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.json
```
El archivo `firebase-service-account.json` **no se commitea** (está en `.gitignore`).

---

## 7. Flujos de Proceso

### 7.1 Proceso de Compra
```
1. Usuario busca productos (GET /busqueda)
2. Agrega productos al carrito (POST /carrito/items)
3. Revisa el carrito (GET /carrito)
4. Realiza checkout (POST /carrito/checkout)
5. Sistema valida stock y saldo de billetera
6. Sistema genera DeliveryOrders (uno por ítem)
7. Sistema vacía el carrito
8. Sistema actualiza stock y descuenta de billetera
```

### 7.2 Proceso de Entrega
```
1. Sistema genera DeliveryOrder al hacer checkout
2. Entregador lista pedidos pendientes (GET /deliveries)
3. Entregador toma un pedido (POST /deliveries/{id}/tomar)
4. Entregador entrega el producto al comprador
5. Entregador marca como entregado (POST /deliveries/{id}/entregar)
6. Sistema registra fecha/hora de entrega y actualiza estado
```

---

## 8. Requisitos No Funcionales

### Seguridad
- Autenticación delegada a Firebase (no se almacenan contraseñas)
- El backend valida el Firebase ID Token en **cada request** protegido
- Encriptación de datos sensibles en la BD local
- Validación de entrada en todos los endpoints
- No loguear datos sensibles (tokens, UIDs, etc.)
- CORS configurado correctamente

### Performance
- Paginación en todos los listados
- Índices en campos de búsqueda frecuente (nombre, categoria, firebase_uid)
- Transacciones atómicas en operaciones críticas (checkout)

### Testing
- Tests orientados al comportamiento esperado, no a la implementación
- Colección Postman con autenticación via token Firebase
- Swagger/OpenAPI disponible en `/docs`

---

## 9. Entregables Requeridos por el Enunciado

- [ ] **Modelo C4** — diagramas de contexto, contenedores y componentes (incluyendo Firebase)
- [ ] **Diagramas UML** — directorio en el repositorio con diagramas del sistema
- [ ] **README.md** — estructurado con instrucciones de setup
- [ ] **Repositorio GitLab** — código fuente + imagen Docker
- [ ] **Scripts de BD** — estructura de personas, usuarios, roles, direcciones, productos
- [ ] **Archivo de configuración** — `.env.example` con todas las variables incluyendo Firebase
- [ ] **Pipeline CI/CD**
- [ ] **Swagger/OpenAPI** — documentación de API (automática con FastAPI en `/docs`)
- [ ] **Colección Postman** — con autenticación via Firebase ID Token

---

## 10. Checklist de Implementación

### Módulo: Administración (Personas, Usuarios, Direcciones)
- [ ] Modelos en BD (Persona, Usuario, Rol, Dirección)
- [ ] Integración Firebase Admin SDK (verificación de token)
- [ ] Endpoints ABM Personas
- [ ] Endpoints ABM Usuarios (con Firebase UID)
- [ ] Endpoints ABM Direcciones
- [ ] Validaciones
- [ ] Tests

### Módulo: Productos
- [ ] Modelo Producto (con relación a Dirección punto de venta)
- [ ] Catálogo de categorías predefinido
- [ ] CRUD de productos
- [ ] Validaciones
- [ ] Tests

### Módulo: Búsqueda
- [ ] Endpoint de búsqueda con filtros y ordenamiento
- [ ] Tests

### Módulo: Billetera Virtual
- [ ] Modelos (BilleteraVirtual, TransaccionBilletera)
- [ ] Ver saldo
- [ ] Cargar saldo
- [ ] Historial de transacciones
- [ ] Validaciones (límite de carga, saldo no negativo)
- [ ] Tests

### Módulo: Carrito + Checkout
- [ ] Modelos (Carrito, CarritoItem)
- [ ] CRUD carrito
- [ ] Proceso de checkout (transacción atómica)
- [ ] Validaciones (stock, saldo billetera)
- [ ] Tests

### Módulo: Delivery
- [ ] Modelo DeliveryOrder
- [ ] Listar pendientes
- [ ] Tomar delivery
- [ ] Marcar entregado
- [ ] Validaciones de estados
- [ ] Tests

### Infraestructura
- [ ] Dockerfile
- [ ] Pipeline CI/CD
- [ ] Alembic migrations
- [ ] Colección Postman
- [ ] Diagramas C4 y UML
