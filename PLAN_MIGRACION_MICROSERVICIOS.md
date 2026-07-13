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

Se auditaron **todos** los imports `from app.modules.X` entre módulos. El grafo de dependencias completo es:

```
carrito/service.py   ──> delivery.models (DeliveryOrder)
                     ──> productos.models (Producto)
                     ──> billetera.service (get_or_create_billetera, descontar_saldo)  [checkout, import diferido]
productos/service.py ──> admin.models (Usuario, Direccion)
busqueda/router.py   ──> productos.service   (solo delega; búsqueda NO es un servicio)
ordenes/service.py   ──> admin, carrito, productos   [MÓDULO MUERTO — excluir, ver §7]
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

Mapeo confirmado (sin cambios respecto al TP):

| Servicio | Módulos | BD propia | Rol en la saga |
|---|---|---|---|
| **Identidad y Acceso** | `admin` | `personas, usuarios, roles, usuario_roles, direcciones` | — (nadie depende de la saga; todos dependen de él por ID) |
| **Catálogo** | `productos` + `busqueda` | `productos, categorias, resenas` | Participante: `ReservarStock`/`LiberarStock` |
| **Carrito & Checkout** | `carrito` | `carritos, carrito_items` + estado de saga | **Orquestador** (`CheckoutSaga`) |
| **Billetera** | `billetera` | `billeteras, transacciones_billetera` | Participante: `DebitarSaldo`/`ReintegrarSaldo` |
| **Delivery** | `delivery` | `delivery_orders` | Participante **pivote**: `CrearDeliveries` |

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

### 5.2. Lo que pide el TP2 (saga por orquestación, async)

| Paso | Servicio | Transacción | Tipo | Compensación |
|---|---|---|---|---|
| 1 | Catálogo | `ReservarStock()` | Compensatable | `LiberarStock()` |
| 2 | Billetera | `DebitarSaldo()` | Compensatable | `ReintegrarSaldo()` |
| 3 | Delivery | `CrearDeliveries()` | **Pivote** (go/no-go) | — |
| 4 | Carrito | `vaciarCarrito()` | Retriable | — |

Rutas de falla: stock insuf. → `409` (sin compensar); saldo insuf. → `LiberarStock` → `402`; falla deliveries → `ReintegrarSaldo`+`LiberarStock` → `500`.

### 5.2.bis. Dos gaps de coherencia detectados al cruzar los TPs con el código

Al contrastar el hexágono de cada servicio (TP Hexagonales §3) con la clasificación de la saga (TP Checkout §6), aparecen dos puntos que hay que **reconciliar antes de implementar** — no invalidan el diseño, pero quedaron sin resolver en el papel:

- **`DescontarStock` está declarado pero la saga nunca lo invoca.** El hexágono de Catálogo lista tres comandos de stock (`ReservarStock` / `DescontarStock` / `LiberarStock`), pero la secuencia de la saga solo usa `ReservarStock` + `LiberarStock` (compensación) y **no muestra cuándo se confirma la reserva** (el "descontar definitivo"). Esto refuerza el punto 1 de §5.3: hay que decidir si `DescontarStock` corre tras el pivote (`CrearDeliveries` OK) o si la reserva simplemente se vuelve permanente. El TP dejó esa confirmación implícita.
- **`CancelarDeliveries` está declarado pero queda muerto.** El hexágono de Delivery declara el handler `CrearDeliveries` / `CancelarDeliveries`, pero como `CrearDeliveries` es el **pivote sin compensación** y el único paso posterior (`vaciarCarrito`) es retriable, no existe ninguna rama de la saga que dispare `CancelarDeliveries`. O se elimina, o se define un escenario de falla post-pivote que lo justifique.

### 5.3. Qué hay que construir (esto es el 90% del esfuerzo)

1. **Separar "reservar" de "confirmar" stock.** Hoy hay un solo `producto.stock -= cantidad`. Hay que introducir stock **reservado** vs **disponible** para que `ReservarStock` sea compensable con `LiberarStock`.
2. **`DebitarSaldo` compensable.** Hoy `descontar_saldo` no commitea; distribuido debe commitear en su propia BD y exponer `ReintegrarSaldo`. Cuidado con reintegros duplicados → idempotencia.
3. **Orquestador `CheckoutSaga`** en Carrito: máquina de estados persistida (`saga_state`: qué pasos completaron, para poder compensar tras un crash).
4. **Outbox** en cada servicio: publicar el comando/evento en la misma transacción local que modifica datos (evita "cambié la BD pero no publiqué").
5. **Idempotencia** en cada handler: un `message_id` + tabla de mensajes procesados (un comando puede reentregarse).
6. **Colas**: cola de comandos por participante + cola de respuestas de la saga (request/reply).

> Recomendación: probar al menos un **caso de fallo end-to-end** (p. ej. saldo insuficiente que dispara `LiberarStock`), tal como plantea el TP2 §5 y §7.

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
| 0 | *(limpieza)* | — | — | Borrar `ordenes`, subir a Py 3.11, elegir broker |
| 1 | **Identidad** | Bajo | ninguna | Hoja pura. Todos lo referencian; empieza acá |
| 2 | **Billetera** | Bajo | Identidad | Autónoma; solo `usuario_id` |
| 3 | **Catálogo** | Medio | Identidad | Resolver `validar_direccion_vendedor` y el `selectinload` de dirección (§3, §4) |
| 4 | **Delivery** | Medio | Identidad, Catálogo | Participante de la saga; expone `CrearDeliveries` |
| 5 | **Carrito & Checkout** | **Alto** | todos | Orquestador + reemplazo del checkout atómico por la saga (§5). Último a propósito |

En cada paso: el monolito enruta al nuevo servicio (proxy) hasta cortar el módulo viejo. Los tests existentes (27) sirven como red de regresión por dominio.

### 8.1. Mapeo de tests por contexto (del TP Hexagonales §6)

Cada microservicio se lleva los tests de su dominio y suma los de sus command handlers de la saga:

| Bounded Context | Tests del TP1 (`tests/unit/`) | A sumar en la migración |
|---|---|---|
| Identidad y Acceso | `admin` | Mock de Firebase en el guard de auth |
| Catálogo | `productos`, `busqueda` | Handlers `ReservarStock`/`LiberarStock` (idempotencia) |
| Carrito & Checkout | `carrito`, `checkout` | Saga: caminos felices y de compensación |
| Billetera | `billetera` | Handler `DebitarSaldo`/`ReintegrarSaldo` |
| Delivery | `delivery` | Handler `CrearDeliveries`/`CancelarDeliveries` |

---

## 9. Infraestructura nueva a decidir

**Message broker** — el TP lo deja agnóstico y menciona tres opciones (Hexagonales §7): **RabbitMQ**, **Kafka** o **SQS**. Para el modelo command channel + reply channel del TP, RabbitMQ es el que más directo calza con request/reply y colas de comandos; Kafka apunta a alto throughput (más pesado para una saga de 3 participantes) y SQS aplica si se despliega en AWS.

Además, transversal a todos: **tabla `outbox`** por servicio, **tabla de idempotencia** (mensajes procesados), **deploy independiente** por microservicio y un **API Gateway** de cara al cliente (como en el mapa de contexto del TP).

---

## 10. Checklist de ejecución

- [ ] Eliminar módulo `ordenes` y sus tablas; subir a Python 3.11.
- [ ] Elegir broker (§9) y levantarlo en `docker-compose`.
- [ ] Extraer **Identidad** con BD propia; monolito consume por HTTP.
- [ ] Extraer **Billetera**; convertir `descontar_saldo`→`DebitarSaldo` con commit propio + `ReintegrarSaldo`.
- [ ] Extraer **Catálogo**; resolver `validar_direccion_vendedor` (§3) y el `selectinload` de dirección (§4); separar stock **reservado** vs **disponible**.
- [ ] Extraer **Delivery**; exponer `CrearDeliveries` (pivote) idempotente.
- [ ] Implementar **`CheckoutSaga`** en Carrito: estado persistido + outbox + idempotencia + compensaciones.
- [ ] Probar end-to-end **un camino de fallo** con compensación real (p. ej. saldo insuficiente → `LiberarStock`).

---

## Resumen (para poder explicar "¿cómo lo evaluaste?")

Medí el acoplamiento real del monolito auditando todos los imports cruzados entre módulos: solo hay **6**, y uno ya está diferido. Eso confirma que los módulos son *vertical slices* casi autónomos, así que separarlos es mecánico y de bajo riesgo. Lo único genuinamente difícil es el **checkout**: hoy es un solo `db.commit()` ACID que Postgres garantiza gratis, y el TP2 pide convertirlo en una **saga orquestada con compensaciones, outbox e idempotencia** — ahí está concentrado el grueso del esfuerzo y del riesgo. Firebase (auth), los UUID (IDs globales) y la estructura por dominio ya juegan a favor. Veredicto: **dificultad media**, con la extracción incremental del §8 dejando el orquestador para el final.
