# SPECS — Migración a Microservicios (Etapa 2)

**Fuente de diseño**: TP Diagramas Hexagonales (23/06/2026) + TP Diagramas de Checkout (30/06/2026).
**Fuente de análisis/plan**: `PLAN_MIGRACION_MICROSERVICIOS.md` (contrastado contra el código real).
**Estado del código**: sigue siendo el **monolito** (TP1 completo). Esta etapa aún no empezó a implementarse.

> Este archivo es el equivalente de `SPECS.md` pero para la etapa de microservicios. `SPECS.md` sigue siendo la fuente de verdad del **monolito** (TP1). Este documento coordina la **migración**.

---

## 🤝 Metodología de Colaboración Entre Agentes

Misma convención que `SPECS.md`. El proyecto lo desarrollan dos personas (Juampi y Nicolas), cada una con su agente Claude.

### Regla principal
**Antes de cada `git push`, el agente activo actualiza la sección "Estado Actual" de este archivo** con qué se implementó, estado de tests, decisiones técnicas y próximos pasos.

### Definición de Hecho (DoD) — al cerrar cada desarrollo/etapa
Ninguna etapa se considera terminada hasta que:
1. **Se prueba todo** (`pytest tests/ -v` completo, no solo los tests nuevos) y queda **verde**. Si el test DB no está levantado, se levanta primero (ver "Correr los tests" abajo) — no vale saltear con `--collect-only`.
2. **Segunda chequeada** de lo recién hecho: releer el diff y contrastarlo contra lo que la etapa pedía (este archivo + `PLAN_MIGRACION_MICROSERVICIOS.md`), verificando que sea **congruente** con el objetivo (nada de más, nada de menos, sin efectos colaterales no buscados).
3. Recién ahí se actualiza "Estado Actual" y se commitea/pushea.

### Correr los tests (Docker — vía oficial del enunciado)
El proyecto **usa Docker** (directiva del enunciado). El `docker-compose.yml` incluye un servicio `test-db` que matchea el default de `tests/conftest.py` (`localhost:5433`, db `compra_venta_test`, pass `pass123`), así `pytest` corre sin setear nada. El schema lo crea `conftest.py` con `Base.metadata.create_all` (no hace falta alembic).
```bash
docker compose up -d test-db      # levanta el Postgres de tests en :5433
pytest tests/ -v                  # usa el default de conftest, sin env vars
docker compose stop test-db       # (opcional) apagar al terminar
```

> **Fallback sin Docker** (solo si Docker no está disponible en la máquina): usar el Postgres nativo en `localhost:5432` creando `compra_venta_test` ahí y apuntando `TEST_DATABASE_URL` a ese puerto. Es un workaround para validar código, **no** la vía oficial.

### Cómo leer este archivo (para el agente que retoma)
1. Leer **primero** la sección "Estado Actual" de acá.
2. Leer `PLAN_MIGRACION_MICROSERVICIOS.md` para el diseño detallado (acoplamiento medido, saga, FKs cross-servicio, gaps de coherencia detectados).
3. Recién después explorar el código.

### Responsabilidad del agente
- El agente que recibe la instrucción de push actualiza "Estado Actual" antes de confirmar.
- Si el agente que retoma encuentra "Estado Actual" desactualizado, lo corrige al terminar su sesión.

---

## 📍 Estado Actual

> Snapshot de handoff entre agentes: **qué se hizo último** y **qué sigue**. Las **Decisiones vigentes** y la **Deuda técnica** son la referencia estable del diseño.

### Último que se hizo — Sesión 2026-07-22 (Nicolas)
- **Servicio 3 (Catálogo) completo** (`services/catalogo/`, puerto `8003`, DBs `catalogo-db` `:5438` / `catalogo-test-db` `:5439`):
  - Estructura hexagonal idéntica a Billetera (adapters/rest, adapters/persistence, core, service). Se llevó `productos` + `busqueda` del monolito (búsqueda sigue siendo capacidad de consulta, no servicio aparte: mismo router).
  - **Stock reservado vs. disponible**: columna nueva `Producto.stock_reservado`; `stock_disponible = stock - stock_reservado` (property). Búsqueda y listados filtran por **disponible** > 0 (un producto con todo su stock reservado por sagas en curso desaparece del catálogo).
  - **Handlers de saga** en `/interno/stock/`: `reservar` (todo-o-nada, compensable), `descontar` (confirma tras el pivote: baja físico + libera reserva), `liberar` (compensación, tolerante a productos inexistentes). Idempotentes por `message_id` vía `MensajeProcesado`; igual que Billetera, solo se registra el message_id cuando el comando **mutó** estado (un rechazo sin efectos se reevalúa al reintentar).
  - **`validar_direccion_vendedor` resuelto con llamada síncrona a Identidad** (`GET /interno/direcciones/{id}`): valida activa + pertenencia (`persona_id` del vendedor). El guard de auth (`get_current_usuario`) devuelve el usuario completo de Identidad porque Catálogo necesita `persona_id`.
  - **Dirección de punto de venta: composición síncrona en lectura** (decisión de Nicolas entre snapshot desnormalizado / composición / réplica por eventos): Catálogo guarda solo `direccion_punto_venta_id` (sin FK) y al servir listados resuelve las direcciones en **una llamada batch** al endpoint nuevo de Identidad `GET /interno/direcciones?ids=...`. Si Identidad no responde, degrada con `direccion_punto_venta: null` en vez de romper la búsqueda.
  - Endpoint interno extra `GET /interno/productos/{id}` (lo van a consumir Carrito y Delivery en las etapas 4-5).
  - FKs cross-service (`vendedor_id`, `direccion_punto_venta_id`, `Resena.usuario_id`) sin constraint físico, como en Billetera.
- **Identidad**: se agregó `GET /interno/direcciones?ids=` (batch) + 2 tests. Cuidado con el orden de rutas: va declarado antes de `/interno/direcciones/{id}`.
- **Tests: todo verde** — Catálogo **25/25** (10 productos + 6 búsqueda + 9 stock/saga), Identidad **14/14**, Billetera **10/10**, monolito **63/63** (112 total), vía `docker compose up -d test-db identidad-test-db billetera-test-db catalogo-test-db`.
- Entorno local de esta máquina: venv con **Python 3.12** (el 3.9 del sistema no compila `cryptography`); `.env` creado desde `.env.example` apuntando a `localhost:5433` (no se commitea). Ojo: el container `pagina-perfumes-no-back-db-1` (otro proyecto) se auto-levanta con Docker y pisa el puerto 5433 — frenarlo antes de correr tests (`docker stop pagina-perfumes-no-back-db-1`).

### Qué sigue
1. **Servicio 4: Delivery** (async post-pivote): exponer `CrearDeliveries` idempotente consumiendo de RabbitMQ, con canales de respuesta múltiples.
2. **Servicio 5: Carrito & Checkout** (orquestador): `CheckoutSaga` (ReservarStock → DebitarSaldo (pivote) → DescontarStock → vaciar carrito → CrearDeliveries async) + log de deliverys + compensación (`LiberarStock`).
3. Al extraer Carrito: probar end-to-end un camino de fallo con compensación real (saldo insuficiente → LiberarStock → 402) y un retry de delivery desde el log (plan §10).

### Decisiones técnicas vigentes
- **Todo hexagonal (ports & adapters).** Cada servicio expone su dominio detrás de puertos, con adaptadores REST / persistencia / Firebase / saga.
- **Comunicación sincrónica salvo Delivery.** Los pasos que bloquean la respuesta del checkout (ReservarStock, DebitarSaldo, DescontarStock, vaciarCarrito) van por **REST/RPC sincrónico** — se espera a todos igual, las colas async no aportan. **Solo Delivery es asincrónico.**
- **Pivote = `DebitarSaldo`** (Billetera), no `CrearDeliveries`. Al ser Delivery async con retry, ya no puede ser el go/no-go.
- **Log local de deliverys** en Carrito (outbox aplicado a delivery): registra los deliverys a enviar para decidir retry vs. no-retry.
- **RabbitMQ — solo para el delivery async**, con **canales de respuesta múltiples** (uno por participante/flujo), no una cola general única.
- **Migración incremental**, no big-bang: un servicio a la vez detrás del monolito-fachada, compilando y testeando en cada paso.
- **Orden de extracción** (del grafo de dependencias): Identidad, Billetera, Catálogo, Delivery, Carrito/Saga.

### Gaps de coherencia — resueltos por el rediseño (ver plan §5.2.bis)
- `DescontarStock` corre tras el pivote (paso 3) para confirmar la reserva de stock. Deja de estar sin uso.
- `ReintegrarSaldo` queda muerto (el pivote `DebitarSaldo` no se compensa) → eliminar o dejar como operación administrativa.
- `CancelarDeliveries` queda muerto (`CrearDeliveries` es async post-pivote con retry) → eliminar o reservar para cancelación administrativa.

### Deuda técnica / problemas conocidos
- ~~Módulo `ordenes` a eliminar~~ → **hecho**.
- ~~Python 3.9 EOL~~ → **hecho** (Dockerfile en 3.11-slim).
- `reservar_stock` no toma lock de fila (`SELECT ... FOR UPDATE`): dos sagas concurrentes sobre el mismo producto podrían sobre-reservar. Mismo comportamiento que tenía el checkout del monolito; agregar `with_for_update()` si se quiere cerrar la ventana.
- La composición síncrona de direcciones acopla la lectura del catálogo a Identidad en runtime (degrada a `direccion: null` si no responde). Si molesta en la demo, el fallback es levantar ambos servicios juntos (`--profile microservices`).
- ~~Re-verificar tests vía Docker~~ → **hecho** (63/63 verde).
- ~~RabbitMQ en docker-compose~~ → **hecho**.
- ~~Esqueleto hexagonal + contratos~~ → **hecho** (`services/shared/contracts/`, estructura identidad/billetera).
- ~~Idempotencia base~~ → **hecho** (`MensajeProcesado` en Billetera).
- ~~Servicio 1: Identidad~~ → **hecho** (12/12 tests).
- ~~Servicio 2: Billetera~~ → **hecho** (10/10 tests, DebitarSaldo idempotente).
- En la notebook, el `.env` **no está en git** → tenerlo local con `ENCRYPTION_KEY` y `FIREBASE_SERVICE_ACCOUNT_PATH`.

---

## 1. Objetivo de la etapa

Migrar el monolito de compra y venta a una arquitectura de **microservicios** (5 bounded contexts, database-per-service), reemplazando el checkout atómico por una **saga orquestada**, según el diseño de los dos TPs.

---

## 2. Alcance

**Dentro:**
- 5 microservicios **hexagonales** (ports & adapters): Identidad y Acceso, Catálogo, Carrito & Checkout, Billetera, Delivery.
- Base de datos propia por servicio.
- FKs cross-módulo pasan a referencia por ID + consistencia eventual.
- Saga de checkout orquestada por Carrito & Checkout, con **log de deliverys** e idempotencia.
- Comunicación: **REST/RPC sincrónico para todo** (consultas y pasos de la saga que bloquean la respuesta) + **RabbitMQ asincrónico solo para Delivery**, con canales de respuesta múltiples.

**Fuera:**
- `notificaciones`: no forma parte de la saga; queda como consumidor puro si más adelante se migra.
- `ordenes`: deuda técnica, se elimina.

---

## 3. Stack Tecnológico (adiciones a esta etapa)

| Capa | Tecnología |
|------|-----------|
| Arquitectura por servicio | **Hexagonal (ports & adapters)** |
| Base del servicio | Python 3.11 + FastAPI (igual que el monolito) |
| BD por servicio | PostgreSQL (una instancia/DB por microservicio) |
| Comunicación entre servicios | **REST/RPC sincrónico** para consultas y pasos de la saga que bloquean |
| **Message broker** | **RabbitMQ — solo para Delivery async**, con canales de respuesta múltiples |
| Orquestación local | Docker Compose (broker + N Postgres + N servicios) |
| Fachada | API Gateway de cara al cliente |
| Confiabilidad | **Log de deliverys** (retry) + idempotencia por servicio |
| Auth | Firebase (sin cambios; cada servicio valida el Bearer) |

---

## 4. Arquitectura objetivo

Detalle completo en `PLAN_MIGRACION_MICROSERVICIOS.md`. Resumen:

| Servicio | Módulo(s) del monolito | Rol en la saga |
|---|---|---|
| **Identidad y Acceso** | `admin` | — (todos lo referencian por ID) |
| **Catálogo** | `productos` + `busqueda` | `ReservarStock` / `LiberarStock` (compensatable) + `DescontarStock` (confirma tras el pivote) |
| **Billetera** | `billetera` | `DebitarSaldo` (**pivote**, go/no-go) |
| **Delivery** | `delivery` | `CrearDeliveries` (**asincrónico** post-pivote, con log + retry) |
| **Carrito & Checkout** | `carrito` | **Orquestador** (`CheckoutSaga`) + `vaciarCarrito` (retriable) |

**Saga (camino feliz), en orden:** ReservarStock (sinc), luego DebitarSaldo (sinc, **pivote**), luego DescontarStock (sinc), luego CrearDeliveries (**async** con log + retry), luego vaciarCarrito (sinc), y responde 200.
**Compensación:** stock insuf. devuelve 409; saldo insuf. dispara `LiberarStock` y devuelve 402. **No hay falla post-pivote** (Delivery es async con retry, no aborta la saga).

---

## 5. Checklist de Implementación

> Extracción incremental: cada etapa queda funcionando (compilar + tests) antes de la siguiente. El monolito hace de fachada hasta que el servicio nuevo reemplaza al módulo viejo.

### Etapa 0 — Preparación e infra base
- [x] Eliminar módulo `ordenes` (código + router en `main.py` + import en `alembic/env.py` + TRUNCATE de `conftest.py` + migración `d2e4f6a8b0c1` que dropea `orden_items`/`ordenes`)
- [x] Subir a Python 3.11 (Dockerfile ya en `python:3.11-slim`; venv y CI corren 3.11.6)
- [x] `docker-compose` con RabbitMQ levantado (solo para el delivery async)
- [x] Definir esqueleto hexagonal reutilizable (puertos + adaptadores REST/persistencia) — ver `services/identidad/` y `services/billetera/` como referencia
- [x] Definir contratos: llamadas sincrónicas (REST) de los pasos de la saga + mensajes async de delivery con **canales de respuesta múltiples** — ver `services/shared/contracts/`
- [x] Base reutilizable de **log de deliverys** (retry) + tabla de idempotencia (`MensajeProcesado` en `services/billetera/app/adapters/persistence/models.py`)

### Servicio 1 — Identidad y Acceso (`admin`)
- [x] Extraer a servicio hexagonal con BD propia (personas, usuarios, roles, usuario_roles, direcciones)
- [x] REST API: ABM personas/usuarios/direcciones
- [x] Firebase Auth adapter (`verify_id_token`)
- [x] Endpoint de consulta de usuario/dirección por ID (para los demás servicios, síncrono REST) — `/interno/usuarios/{id}`, `/interno/usuarios/by-firebase/{uid}`, `/interno/direcciones/{id}`
- [x] Tests: 7 admin + 5 interno = **12/12 verde**

### Servicio 2 — Billetera (`billetera`) — **pivote de la saga**
- [x] Extraer a servicio hexagonal con BD propia (billeteras, transacciones_billetera, mensajes_procesados)
- [x] REST API: cargar / consultar saldo e historial
- [x] `DebitarSaldo` como endpoint **sincrónico** e idempotente (por `message_id`), con commit propio — es el **pivote** (go/no-go). Devuelve `SaldoRespuesta(ok, saldo_resultante, error)`.
- [x] Auth pública: verifica Firebase → llama a Identidad `/interno/usuarios/by-firebase/{uid}` para resolver `usuario_id`
- [x] `usuario_id` en `billeteras` sin FK física (referencia cross-service por ID)
- [x] `ReintegrarSaldo`: excluido (queda muerto con el pivote en Billetera)
- [x] Tests: 6 billetera + 4 debitar (idempotencia, saldo insuf., transacción) = **10/10 verde**

### Servicio 3 — Catálogo (`productos` + `busqueda`)
- [ ] Extraer a servicio hexagonal con BD propia (productos, categorias, resenas)
- [ ] REST API: catálogo, búsqueda (stock > 0), reseñas
- [ ] Resolver `validar_direccion_vendedor` (llamada sincrónica a Identidad o réplica de direcciones)
- [ ] Resolver el `selectinload(Producto.direccion_punto_venta)` cross-servicio
- [ ] Introducir stock **reservado** vs **disponible**
- [ ] Endpoints **sincrónicos** e idempotentes: `ReservarStock` (compensable) / `DescontarStock` (confirma tras el pivote) / `LiberarStock` (compensación)
- [ ] `DescontarStock` corre como **paso 3** (tras `DebitarSaldo` OK) — gap resuelto (plan §5.2.bis)
- [ ] Respuesta sincrónica: stock reservado OK / stock insuficiente (409)
- [ ] Tests: dominio + `ReservarStock`/`LiberarStock`/`DescontarStock`

### Servicio 4 — Delivery (`delivery`) — **asincrónico post-pivote**
- [ ] Extraer a servicio hexagonal con BD propia (delivery_orders)
- [ ] REST API: mis-asignados / tomar / entregar
- [ ] `Delivery command handler` **asincrónico**: `CrearDeliveries` idempotente (consume de RabbitMQ; el orquestador lo respalda con el log de deliverys + retry)
- [ ] Confirmación por **canal de respuesta propio** (no cola general): `DeliveriesCreadas`
- [ ] `CancelarDeliveries`: **fuera de la saga** (queda muerto con delivery async + retry) — eliminar o dejar como operación administrativa
- [ ] Tests: dominio + handler `CrearDeliveries` (idempotencia)

### Servicio 5 — Carrito & Checkout (`carrito`) — orquestador
- [ ] Extraer a servicio hexagonal con BD propia (carritos, carrito_items) + estado de saga + **log de deliverys**
- [ ] REST API: operaciones del carrito + `checkout()`
- [ ] `CheckoutSaga`: máquina de estados persistida (para compensar `ReservarStock` si falla el débito, o retomar los pasos post-pivote tras un crash)
- [ ] Adaptador de salida **sincrónico** (REST/RPC) a Catálogo (ReservarStock/DescontarStock) y Billetera (DebitarSaldo)
- [ ] Adaptador de salida **asincrónico** a Delivery: persistir el **log de deliverys** y despachar con retry; consumir los **canales de respuesta múltiples**
- [ ] Compensación (`LiberarStock`) + códigos HTTP (409 / 402)
- [ ] Tests: saga camino feliz + compensación (saldo insuf. → `LiberarStock` → 402) + **retry de delivery** desde el log

### Infra transversal
- [ ] API Gateway de cara al cliente
- [ ] `docker-compose` completo (broker + 5 Postgres + 5 servicios + gateway)

---

## 6. Referencias

- `PLAN_MIGRACION_MICROSERVICIOS.md` — análisis, dificultad, acoplamiento medido, saga, FKs, gaps de coherencia.
- `TP_Diagramas_Hexagonales.pdf` — 5 hexágonos + mapa de contexto + tests por contexto.
- `TP_Diagramas_Checkout.pdf` — máquina de estados, secuencia ok/fallida, compensación, interacción con broker.
- `SPECS.md` — fuente de verdad del **monolito** (TP1).
- `CONTEXT.md` — modelo de datos real y decisiones técnicas del monolito.
