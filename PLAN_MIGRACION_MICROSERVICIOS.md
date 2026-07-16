# Plan de migración a microservicios — `compra-y-venta-monolito`

> Evaluación de viabilidad + plan incremental, contrastando el diseño de los dos TPs
> (Hexagonales + Checkout/Saga) contra el **código real** del monolito.
> Fecha: 2026-07-13. Fuente de verdad del estado: `CONTEXT.md` + código en `app/`.

---

## 0. Veredicto: ¿qué tan difícil está?

**Dificultad global: MEDIA. El diseño es sólido y el monolito está bien preparado para esto.** La mayor parte del trabajo (separar dominios) es mecánica y de bajo riesgo. El grueso de la dificultad se concentra en la saga del checkout.

| Dimensión | Dificultad | Por qué |
|---|---|---|
| Separar dominios en servicios | **Baja** | Los módulos ya son *vertical slices* (`models/schemas/service/router`). El acoplamiento cruzado es mínimo (ver §1). |
| Auth por servicio | **Nula** | Ya delegada a Firebase. Cada servicio valida el `Bearer` solo. Nada que migrar. |
| IDs / claves | **Nula** | Todos los PK son UUID. Sin colisiones ni secuencias que coordinar. |
| Reemplazar FKs físicas por referencia-por-ID | **Baja-Media** | Muchas FKs, pero mecánico. Solo **una** cruza con lógica de negocio (§3). |
| Consultas cross-servicio (joins/`selectinload`) | **Media** | Un solo punto real: Catálogo necesita datos de dirección de Identidad (§4). |
| **Checkout atómico → saga distribuida** | **ALTA** | Punto de mayor riesgo. Un `db.commit()` ACID gratis pasa a saga con compensaciones, outbox e idempotencia (§5). |
| Infra nueva (broker, outbox, deploy x5) | **Media** | Trabajo de plataforma más que de dominio. Costo fijo. |

**Conclusión:** migrar los 4 servicios "simples" (Identidad, Billetera, Catálogo, Delivery) es alcanzable y de bajo riesgo. El checkout como saga es el trabajo grande y de mayor riesgo, y conviene reservarlo para el final.

---

## 1. Acoplamiento real medido en el código

Se auditaron **todos** los imports `from app.modules.X` entre módulos. El grafo de dependencias completo (sin flechas: se lista, para cada módulo origen, de qué depende):

```
carrito/service.py      depende de: delivery.models (DeliveryOrder)
                                    productos.models (Producto)
                                    billetera.service (get_or_create_billetera, descontar_saldo)  [checkout, import diferido]
productos/service.py    depende de: admin.models (Usuario, Direccion)
busqueda/router.py      depende de: productos.service   (solo delega; búsqueda NO es un servicio)
ordenes/service.py      depende de: admin, carrito, productos   [MÓDULO MUERTO — excluir, ver §7]
```

Eso es **todo** el acoplamiento cruzado. Ningún otro módulo importa a otro. Esto confirma punto por punto el mapeo del TP (5 servicios) y explica por qué la separación es barata:

- `admin` (→ **Identidad**): no importa a nadie. Hoja del grafo. Se extrae primero sin fricción.
- `billetera` (→ **Billetera**): no importa a nadie. Solo lo consume `carrito` en el checkout.
- `productos`+`busqueda` (→ **Catálogo**): solo dependen de `admin` (Identidad). Un único punto de contacto.
- `delivery` (→ **Delivery**): no importa a nadie; lo consume `carrito` en el checkout.
- `carrito` (→ **Carrito & Checkout**): el hub. Concentra 3 de las 4 dependencias cruzadas del sistema. Por eso es el último y el orquestador.

> **Dato:** el `import` de billetera dentro de `checkout()` es **diferido** (`carrito/service.py:173`) y es la única dependencia de `carrito` hacia `billetera`. Coincide con la frontera de la saga.

---

## 2. Arquitectura objetivo (validada contra el repo)

**Todos los servicios son hexagonales (ports & adapters).** Cada uno expone su dominio detrás de puertos y lo conecta al mundo con adaptadores: adaptador REST de entrada (API), adaptador de persistencia (su BD propia), adaptador Firebase (auth) y —donde participa de la saga— adaptadores de comando/respuesta. La saga se orquesta contra esos puertos, nunca contra tablas de otro servicio.

Mapeo confirmado (rol en la saga **actualizado**: el pivote pasó de Delivery a Billetera, ver §5):

| Servicio | Módulos | BD propia | Rol en la saga |
|---|---|---|---|
| **Identidad y Acceso** | `admin` | `personas, usuarios, roles, usuario_roles, direcciones` | — (nadie depende de la saga; todos dependen de él por ID) |
| **Catálogo** | `productos` + `busqueda` | `productos, categorias, resenas` | Participante: `ReservarStock`/`LiberarStock` (compensatable) + `DescontarStock` (confirma tras el pivote) |
| **Carrito & Checkout** | `carrito` | `carritos, carrito_items` + estado de saga + **log de deliverys** | **Orquestador** (`CheckoutSaga`) |
| **Billetera** | `billetera` | `billeteras, transacciones_billetera` | Participante **pivote** (go/no-go): `DebitarSaldo` |
| **Delivery** | `delivery` | `delivery_orders` | Participante **asincrónico** post-pivote: `CrearDeliveries` (con log + retry) |

Fuera de alcance: `notificaciones` (consumidor de eventos; hoy sin uso en la saga) y `ordenes` (deuda técnica — **eliminar**, §7).

---

## 3. FKs físicas que cruzan límites de servicio

Con *database-per-service* estas FK ya no pueden ser físicas → pasan a **referencia por ID + consistencia eventual**. Inventario completo desde el modelo real:

| FK en el código | Servicio origen → destino | ¿Tiene lógica de negocio? |
|---|---|---|
| `Producto.vendedor_id` | Catálogo → Identidad | No (solo referencia) |
| `Producto.direccion_punto_venta_id` | Catálogo → Identidad | **Sí** — ver abajo |
| `Resena.usuario_id` | Catálogo → Identidad | No |
| `Carrito.usuario_id` | Carrito → Identidad | No |
| `CarritoItem.producto_id` | Carrito → Catálogo | No (validación en agregar/checkout) |
| `BilleteraVirtual.usuario_id` | Billetera → Identidad | No |
| `DeliveryOrder.comprador_id` / `entregador_id` | Delivery → Identidad | No |
| `DeliveryOrder.producto_id` | Delivery → Catálogo | No |
| `DeliveryOrder.direccion_punto_venta_id` | Delivery → Identidad | No |
| `Notificacion.usuario_id` | (Notif) → Identidad | Ya es **lógica, sin FK física** ✅ |

La mayoría son referencias planas: quitar la `ForeignKey(...)` del modelo, dejar la columna UUID, y validar (si hace falta) con una llamada al servicio dueño. Trabajo mecánico.

**La única con lógica de negocio real** está en `productos/service.py:80-88`:

```python
async def validar_direccion_vendedor(db, direccion_id, vendedor):
    direccion = ... select(Direccion).where(Direccion.id == direccion_id)
    if direccion.persona_id != vendedor.persona_id:
        raise ValueError("La dirección no pertenece al vendedor")
```

Catálogo hoy lee la tabla `direcciones` (de Identidad) para validar que el punto de venta pertenece al vendedor. Distribuido, esto se resuelve con **una llamada síncrona a Identidad** o replicando las direcciones del vendedor en Catálogo. Es el único lugar donde una regla de negocio cruza el límite Catálogo↔Identidad.

---

## 4. Consultas cross-servicio (joins / `selectinload`)

Auditadas todas las cargas de relaciones que cruzan módulos:

- **`Producto.direccion_punto_venta`** (`productos/service.py:29,69,107,117`): la búsqueda y el detalle de producto devuelven la dirección completa del punto de venta vía `selectinload`. Esa dirección vive en Identidad. **Este es el único join cross-servicio del sistema.** Opciones al distribuir:
  1. **Replicar** en Catálogo los campos de dirección que la UI necesita (desnormalización, actualizada desde Identidad).
  2. **Llamada síncrona** a Identidad al servir la búsqueda (composición en el gateway o en Catálogo). Más simple, peor latencia en listados.
- **`carrito.items` / `Producto`**: en el checkout, Carrito lee `Producto.stock` y `direccion_punto_venta_id` (`carrito/service.py:182,211`). Esto **desaparece** al pasar a la saga: Carrito ya no lee la tabla de productos; le manda el comando `ReservarStock` a Catálogo y Catálogo responde.
- **`busqueda`**: no tiene queries propias, solo delega en `productos_service`. Confirma que "búsqueda es una capacidad de consulta, no un servicio". Cero trabajo de separación.

---

## 5. El corazón del problema: checkout atómico → saga

### 5.1. Lo que hay hoy (ACID gratis)

`carrito/service.py:170-243`, un **único `db.commit()`** que hace, todo-o-nada:

1. Carga carrito + valida no vacío.
2. Valida stock por ítem y carga productos.
3. Calcula total con descuento.
4. Verifica saldo (`get_or_create_billetera`).
5. Crea un `DeliveryOrder` por ítem **y** descuenta stock (`producto.stock -= cantidad`).
6. Descuenta saldo (`descontar_saldo`, **sin commit propio** — comparte la transacción).
7. Vacía carrito.
8. `db.commit()` único.

Postgres garantiza la atomicidad **gratis**. Fíjate que `descontar_saldo` ya está diseñada "sin commit propio" para participar del commit del carrito — ese patrón es justo el que se rompe al distribuir.

### 5.2. La saga por orquestación (revisada: sincrónica salvo delivery)

**Modelo de comunicación revisado.** El checkout tiene que esperar el resultado de cada paso igual, así que **no se usan colas asíncronas** para los pasos que bloquean la respuesta: el orquestador llama a Catálogo y Billetera con una **conexión sincrónica (REST/RPC)** y espera. El **único paso asincrónico es Delivery**: se dispara después del pivote, se registra en un **log local de deliverys** y se reintenta hasta confirmar, sin bloquear la respuesta del checkout.

**El pivote pasó de `CrearDeliveries` a `DebitarSaldo`.** Como Delivery ahora es asincrónico con retry, ya no puede ser el punto go/no-go de la saga. El punto de no retorno es el débito de saldo: si el saldo se debita, la compra procede; lo que viene después (confirmar stock, crear deliveries, vaciar carrito) es post-pivote y no falla la saga.

| Paso | Servicio | Comunicación | Tipo | Compensación |
|---|---|---|---|---|
| 1 | Catálogo | Sincrónica | `ReservarStock()` — Compensatable | `LiberarStock()` |
| 2 | Billetera | Sincrónica | `DebitarSaldo()` — **Pivote** (go/no-go) | — |
| 3 | Catálogo | Sincrónica | `DescontarStock()` — Retriable (confirma la reserva) | — |
| 4 | Delivery | **Asincrónica** | `CrearDeliveries()` — log local + retry | — |
| 5 | Carrito | Sincrónica | `vaciarCarrito()` — Retriable | — |

Rutas de falla: stock insuf. produce `409` (sin compensar); saldo insuf. dispara `LiberarStock` y produce `402`. **No hay falla post-pivote**: una vez debitado el saldo, `DescontarStock`, `CrearDeliveries` (async con retry) y `vaciarCarrito` son retriables y siempre terminan confirmando.

### 5.2.bis. Gaps de coherencia — resueltos por el rediseño

El cruce de los hexágonos (TP Hexagonales §3) con la saga (TP Checkout §6) había dejado dos comandos declarados sin uso. El rediseño (pivote en Billetera + delivery async) los resuelve:

- **`DescontarStock` ahora tiene lugar claro:** corre como **paso 3**, tras el pivote (`DebitarSaldo` OK), para confirmar la reserva de stock y volverla permanente. Deja de estar implícito.
- **`ReintegrarSaldo` queda muerto** con el pivote en Billetera: `DebitarSaldo` es el punto de no retorno y nada posterior lo compensa. Se puede **eliminar** del hexágono de Billetera (o dejarlo solo como operación administrativa fuera de la saga).
- **`CancelarDeliveries` queda muerto:** `CrearDeliveries` es post-pivote, asincrónico y con retry (nunca aborta la saga). Se **elimina**, o se reserva para un flujo administrativo de cancelación ajeno a la saga.

### 5.3. Qué hay que construir (esto es el 90% del esfuerzo)

1. **Separar "reservar" de "confirmar" stock.** Hoy hay un solo `producto.stock -= cantidad`. Hay que introducir stock **reservado** vs **disponible**: `ReservarStock` (compensable con `LiberarStock`) y `DescontarStock` (confirma la reserva tras el pivote).
2. **`DebitarSaldo` como pivote.** Hoy `descontar_saldo` no commitea; distribuido debe commitear en su propia BD al debitar. Es el punto de no retorno de la saga; con idempotencia por `message_id` para no debitar dos veces si el orquestador reintenta la llamada sincrónica.
3. **Orquestador `CheckoutSaga`** en Carrito: máquina de estados persistida (`saga_state`: qué pasos completaron, para poder compensar `ReservarStock` si falla el débito, o retomar los pasos post-pivote tras un crash).
4. **Log local de deliverys** en Carrito (patrón outbox aplicado a Delivery): antes de responder, la saga persiste en su propia BD los deliverys a crear; un despachador async los envía a Delivery y los reintenta según el log hasta confirmar. Es el mecanismo que decide retry vs. no-retry.
5. **Idempotencia** en los handlers reentregables (`DebitarSaldo`, `DescontarStock`, `CrearDeliveries`): un `message_id` + tabla de mensajes procesados (un comando puede reintentarse, sea por reintento sincrónico o por el retry del log de delivery).
6. **Canales de respuesta múltiples (no una cola general única)** para la parte asincrónica de delivery: en vez de una sola cola de respuestas de la saga, se generan **varios canales de respuesta** (uno por participante/flujo de delivery) para que las confirmaciones no se mezclen. El resto de los pasos, al ser sincrónicos, no usan colas.

> Recomendación: probar al menos un **caso de fallo end-to-end** (p. ej. saldo insuficiente que dispara `LiberarStock` y devuelve `402`), y un caso de **retry de delivery** (una entrega que falla la primera vez y el log la reintenta).

---

## 6. Lo que ya juega a favor (no tocar)

- **Auth = Firebase.** Cada servicio valida el `Bearer <id_token>` por su cuenta (`app/core/dependencies.py`, `firebase.py`). Cero trabajo de identidad distribuida.
- **PKs UUID globales** en todo. IDs únicos entre servicios sin coordinación.
- **Vertical slices** con `service.py` separado del router: la lógica ya está encapsulada por dominio; extraer = mover carpeta + darle su BD.
- **`Notificacion.usuario_id` ya es lógico** (sin FK física): patrón de referencia-por-ID ya presente en el repo.
- **Acoplamiento cruzado mínimo** (§1): 6 imports cruzados en total, y uno ya es diferido.

---

## 7. Pre-requisito: limpiar deuda antes de migrar

- **Eliminar el módulo `ordenes`.** No es parte del TP, genera tablas extra y **acopla** `admin`+`carrito`+`productos` (§1). Sacarlo simplifica el grafo antes de cortar. Borrar `app/modules/ordenes/`, su router en `main.py` y las tablas de la migración.
- **Definir `notificaciones` como consumidor puro** (fuera de la saga) o dejarlo en Identidad por ahora.
- Python 3.11+ (3.9 EOL) para las imágenes de los servicios.

---

## 8. Orden de extracción (incremental, un servicio a la vez, sin big-bang)

Los TPs no prescriben un orden de extracción; el siguiente sale del grafo de dependencias real (§1): extraer siempre una **hoja** primero, con el monolito haciendo de fachada.

| # | Servicio | Riesgo | Dependencias (por ID) | Notas |
|---|---|---|---|---|
| 0 | *(limpieza)* | — | — | Borrar `ordenes`, subir a Py 3.11, levantar broker (solo para delivery async) |
| 1 | **Identidad** | Bajo | ninguna | Hoja pura. Todos lo referencian; empieza acá |
| 2 | **Billetera** | Bajo | Identidad | Autónoma; solo `usuario_id`. Será el **pivote** (`DebitarSaldo`) |
| 3 | **Catálogo** | Medio | Identidad | Resolver `validar_direccion_vendedor` y el `selectinload` de dirección (§3, §4) |
| 4 | **Delivery** | Medio | Identidad, Catálogo | Participante **asincrónico** post-pivote; expone `CrearDeliveries` idempotente (el orquestador lo maneja con log + retry) |
| 5 | **Carrito & Checkout** | **Alto** | todos | Orquestador + reemplazo del checkout atómico por la saga (§5), con log de deliverys. Último a propósito |

En cada paso: el monolito enruta al nuevo servicio (proxy) hasta cortar el módulo viejo. Los tests existentes (27) sirven como red de regresión por dominio.

### 8.1. Mapeo de tests por contexto (del TP Hexagonales §6)

Cada microservicio se lleva los tests de su dominio y suma los de sus command handlers de la saga:

| Bounded Context | Tests del TP1 (`tests/unit/`) | A sumar en la migración |
|---|---|---|
| Identidad y Acceso | `admin` | Mock de Firebase en el guard de auth |
| Catálogo | `productos`, `busqueda` | Handlers `ReservarStock`/`LiberarStock` (idempotencia) |
| Carrito & Checkout | `carrito`, `checkout` | Saga: camino feliz, compensación (`LiberarStock`) y **retry del log de deliverys** |
| Billetera | `billetera` | Handler `DebitarSaldo` (pivote, idempotente) |
| Delivery | `delivery` | Handler `CrearDeliveries` (asincrónico, idempotente) |

---

## 9. Infraestructura nueva a decidir

**Comunicación mayormente sincrónica.** Los pasos de la saga que bloquean la respuesta del checkout (ReservarStock, DebitarSaldo, DescontarStock, vaciarCarrito) se hacen con **conexión sincrónica REST/RPC** entre servicios: como el checkout tiene que esperar a todos igual, las colas asíncronas agregan complejidad sin beneficio. Las consultas de usuario (catálogo, búsqueda, saldo) también son REST síncronas.

**Message broker — solo para el delivery asincrónico.** El único tramo async es `CrearDeliveries`. El TP deja el broker agnóstico (Hexagonales §7: **RabbitMQ**, **Kafka** o **SQS**); **RabbitMQ** es el elegido por calzar directo con **canales de respuesta múltiples** (uno por participante/flujo de delivery, en vez de una única cola general de respuestas). Sobre este broker corre el envío de deliverys respaldado por el **log local de deliverys** (retry).

Además, transversal: **log de deliverys** en Carrito (outbox aplicado a delivery), **tabla de idempotencia** (mensajes procesados) en los handlers reentregables, **deploy independiente** por microservicio y un **API Gateway** de cara al cliente (como en el mapa de contexto del TP).

---

## 10. Checklist de ejecución

- [ ] Eliminar módulo `ordenes` y sus tablas; subir a Python 3.11.
- [ ] Levantar broker (RabbitMQ, §9) en `docker-compose` — solo para el delivery async, con canales de respuesta múltiples.
- [ ] Extraer **Identidad** con BD propia; monolito consume por HTTP síncrono.
- [ ] Extraer **Billetera**; convertir `descontar_saldo` en `DebitarSaldo` (**pivote**) con commit propio e idempotencia.
- [ ] Extraer **Catálogo**; resolver `validar_direccion_vendedor` (§3) y el `selectinload` de dirección (§4); separar stock **reservado** vs **disponible** (`ReservarStock`/`DescontarStock`/`LiberarStock`).
- [ ] Extraer **Delivery**; exponer `CrearDeliveries` asincrónico e idempotente.
- [ ] Implementar **`CheckoutSaga`** en Carrito: estado persistido + llamadas sincrónicas a Catálogo/Billetera + **log de deliverys** (retry) + idempotencia + compensación (`LiberarStock`).
- [ ] Probar end-to-end **un camino de fallo** con compensación real (saldo insuficiente → `LiberarStock` → `402`) y **un retry de delivery** desde el log.

---

## Resumen (para poder explicar "¿cómo lo evaluaste?")

Medí el acoplamiento real del monolito auditando todos los imports cruzados entre módulos: solo hay **6**, y uno ya está diferido. Eso confirma que los módulos son *vertical slices* casi autónomos, así que separarlos es mecánico y de bajo riesgo. Lo único genuinamente difícil es el **checkout**: hoy es un solo `db.commit()` ACID que Postgres garantiza gratis, y hay que convertirlo en una **saga orquestada, hexagonal**, con estos criterios: comunicación **sincrónica** para los pasos que bloquean la respuesta (el checkout espera a todos igual) y **asincrónica solo para Delivery**, respaldado por un **log local de deliverys** que decide los reintentos; el **pivote es `DebitarSaldo`** (punto de no retorno), con `LiberarStock` como única compensación real; y **canales de respuesta múltiples** (no una cola general) para el tramo async. Firebase (auth), los UUID (IDs globales) y la estructura por dominio ya juegan a favor. Veredicto: **dificultad media**, con la extracción incremental del §8 dejando el orquestador para el final.
