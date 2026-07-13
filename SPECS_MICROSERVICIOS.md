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

### Cómo leer este archivo (para el agente que retoma)
1. Leer **primero** la sección "Estado Actual" de acá.
2. Leer `PLAN_MIGRACION_MICROSERVICIOS.md` para el diseño detallado (acoplamiento medido, saga, FKs cross-servicio, gaps de coherencia detectados).
3. Recién después explorar el código.

### Responsabilidad del agente
- El agente que recibe la instrucción de push actualiza "Estado Actual" antes de confirmar.
- Si el agente que retoma encuentra "Estado Actual" desactualizado, lo corrige al terminar su sesión.

---

## 📍 Estado Actual

### Sesión 2026-07-13 — Etapa 2 arranca (Juampi) — **DISEÑO LISTO, IMPLEMENTACIÓN NO INICIADA**

**Qué hay hasta acá:**
- **Monolito TP1 completo** (27/27 tests). Ver `SPECS.md`.
- **Diseño de microservicios terminado en papel** (dos TPs): 5 bounded contexts hexagonales + saga de checkout orquestada. PDFs en la raíz.
- **Plan de migración creado** (`PLAN_MIGRACION_MICROSERVICIOS.md`): evaluación de dificultad (MEDIA), acoplamiento real medido en el código, orden de extracción incremental, y dos gaps de coherencia detectados en los propios TPs (ver abajo).

**Estado de los tests:** 27/27 pasando (los del monolito). Sin tests de microservicios todavía.

**Decisiones técnicas tomadas en esta etapa:**
- **Message broker: RabbitMQ.** Es el que más directo calza con el modelo command channel + reply channel del TP (el TP lo deja agnóstico: Rabbit/Kafka/SQS).
- **Migración incremental**, no big-bang: se extrae un servicio a la vez detrás del monolito-fachada, compilando y testeando en cada paso.
- **Orden de extracción** (derivado del grafo de dependencias, §Arquitectura): Identidad → Billetera → Catálogo → Delivery → Carrito/Saga.

**Gaps de coherencia a resolver antes de implementar** (detectados al cruzar los TPs con el código, ver plan §5.2.bis):
- `DescontarStock` está en el hexágono de Catálogo pero la saga nunca lo invoca → falta definir cuándo se confirma la reserva.
- `CancelarDeliveries` está en el hexágono de Delivery pero, siendo `CrearDeliveries` el pivote, ninguna rama lo dispara → definir o eliminar.

**Próximos pasos sugeridos:** empezar por la **Etapa 0** (limpieza + infra base) y luego **Identidad**. Ver Checklist más abajo.

**Problemas conocidos / deuda técnica:**
- Módulo `ordenes` a eliminar antes de cortar (acopla admin+carrito+productos, fuera del TP).
- Python 3.9 EOL → subir a 3.11 para las imágenes de los servicios.

---

## 1. Objetivo de la etapa

Migrar el monolito de compra y venta a una arquitectura de **microservicios** (5 bounded contexts, database-per-service), reemplazando el checkout atómico por una **saga orquestada**, según el diseño de los dos TPs.

---

## 2. Alcance

**Dentro:**
- 5 microservicios: Identidad y Acceso, Catálogo, Carrito & Checkout, Billetera, Delivery.
- Base de datos propia por servicio.
- FKs cross-módulo → referencia por ID + consistencia eventual.
- Saga de checkout orquestada por Carrito & Checkout, con outbox e idempotencia.
- Comunicación: REST síncrono (user/consultas) + RabbitMQ async (comandos/respuestas de la saga).

**Fuera:**
- `notificaciones`: no forma parte de la saga; queda como consumidor puro si más adelante se migra.
- `ordenes`: deuda técnica, se elimina.

---

## 3. Stack Tecnológico (adiciones a esta etapa)

| Capa | Tecnología |
|------|-----------|
| Base del servicio | Python 3.11 + FastAPI (igual que el monolito) |
| BD por servicio | PostgreSQL (una instancia/DB por microservicio) |
| **Message broker** | **RabbitMQ** (command channel + reply channel) |
| Orquestación local | Docker Compose (broker + N Postgres + N servicios) |
| Fachada | API Gateway de cara al cliente |
| Confiabilidad | Patrón Outbox + idempotencia por servicio |
| Auth | Firebase (sin cambios; cada servicio valida el Bearer) |

---

## 4. Arquitectura objetivo

Detalle completo en `PLAN_MIGRACION_MICROSERVICIOS.md`. Resumen:

| Servicio | Módulo(s) del monolito | Rol en la saga |
|---|---|---|
| **Identidad y Acceso** | `admin` | — (todos lo referencian por ID) |
| **Catálogo** | `productos` + `busqueda` | `ReservarStock` / `LiberarStock` (compensatable) |
| **Billetera** | `billetera` | `DebitarSaldo` / `ReintegrarSaldo` (compensatable) |
| **Delivery** | `delivery` | `CrearDeliveries` (**pivote**) |
| **Carrito & Checkout** | `carrito` | **Orquestador** (`CheckoutSaga`) + `vaciarCarrito` (retriable) |

**Saga (camino feliz):** ReservarStock → DebitarSaldo → CrearDeliveries → vaciarCarrito → 200.
**Compensaciones:** stock insuf. → 409; saldo insuf. → LiberarStock → 402; falla deliveries → ReintegrarSaldo + LiberarStock → 500.

---

## 5. Checklist de Implementación

> Extracción incremental: cada etapa queda funcionando (compilar + tests) antes de la siguiente. El monolito hace de fachada hasta que el servicio nuevo reemplaza al módulo viejo.

### Etapa 0 — Preparación e infra base
- [ ] Eliminar módulo `ordenes` (código + tablas de la migración + router en `main.py`)
- [ ] Subir a Python 3.11
- [ ] `docker-compose` con RabbitMQ levantado
- [ ] Definir contratos de mensajes (comandos y replies de la saga)
- [ ] Base reutilizable de Outbox + tabla de idempotencia (mensajes procesados)

### Servicio 1 — Identidad y Acceso (`admin`)
- [ ] Extraer a servicio con BD propia (personas, usuarios, roles, usuario_roles, direcciones)
- [ ] REST API: ABM + registro/auto-registro
- [ ] Firebase Auth adapter (`verify_id_token`)
- [ ] Endpoint de consulta de usuario/dirección por ID (para los demás servicios, síncrono REST)
- [ ] Tests: dominio `admin` + mock de Firebase en el guard

### Servicio 2 — Billetera (`billetera`)
- [ ] Extraer a servicio con BD propia (billeteras, transacciones_billetera)
- [ ] REST API: cargar / consultar saldo e historial
- [ ] `Saldo command handler` ← Billetera cmd channel: `DebitarSaldo` / `ReintegrarSaldo` (idempotentes)
- [ ] `DebitarSaldo` con commit propio (hoy `descontar_saldo` no commitea)
- [ ] SagaReply: `SaldoDebitado` / `SaldoInsuficiente`
- [ ] Tests: dominio + handlers

### Servicio 3 — Catálogo (`productos` + `busqueda`)
- [ ] Extraer a servicio con BD propia (productos, categorias, resenas)
- [ ] REST API: catálogo, búsqueda (stock > 0), reseñas
- [ ] Resolver `validar_direccion_vendedor` (llamada síncrona a Identidad o réplica de direcciones)
- [ ] Resolver el `selectinload(Producto.direccion_punto_venta)` cross-servicio
- [ ] Introducir stock **reservado** vs **disponible**
- [ ] `Stock command handler`: `ReservarStock` / `DescontarStock` / `LiberarStock` (idempotentes)
- [ ] **Definir cuándo corre `DescontarStock`** (gap de coherencia, plan §5.2.bis)
- [ ] SagaReply: `StockReservado` / `StockInsuficiente`
- [ ] Tests: dominio + handlers `ReservarStock`/`LiberarStock`

### Servicio 4 — Delivery (`delivery`)
- [ ] Extraer a servicio con BD propia (delivery_orders)
- [ ] REST API: mis-asignados / tomar / entregar
- [ ] `Delivery command handler`: `CrearDeliveries` (pivote)
- [ ] **Decidir `CancelarDeliveries`** (gap de coherencia: queda muerto con el pivote actual, plan §5.2.bis)
- [ ] SagaReply: `DeliveriesCreadas`
- [ ] Tests: dominio + handler

### Servicio 5 — Carrito & Checkout (`carrito`) — orquestador
- [ ] Extraer a servicio con BD propia (carritos, carrito_items) + estado de saga
- [ ] REST API: operaciones del carrito + `checkout()`
- [ ] `CheckoutSaga`: máquina de estados persistida (para compensar tras un crash)
- [ ] Outbound command adapter → Catálogo / Billetera / Delivery cmd channels
- [ ] SagaReply consumer ← Checkout saga reply channel
- [ ] Compensaciones + códigos HTTP (409 / 402 / 500)
- [ ] Tests: saga camino feliz + al menos un camino de compensación (TP2 §5, §7)

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
