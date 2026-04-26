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
