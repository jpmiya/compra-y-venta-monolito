# UML — Secuencia del checkout distribuido (CheckoutSaga)

Reemplazo del checkout ACID del monolito por una saga por orquestación.
Todos los comandos llevan `message_id` determinístico (`uuid5(saga_id, paso)`) y
los participantes son idempotentes: cualquier reintento es seguro.

## Camino feliz

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant G as Gateway
    participant CA as Carrito (orquestador)
    participant CAT as Catálogo
    participant B as Billetera
    participant MQ as RabbitMQ
    participant D as Delivery

    C->>G: POST /carrito/checkout {direccion_entrega}
    G->>CA: proxy
    CA->>CA: persistir SagaCheckout (iniciada)
    CA->>CAT: ReservarStock(message_id, items)
    CAT-->>CA: ok (stock_reservado += n)
    CA->>CA: saga → stock_reservado
    CA->>B: DebitarSaldo(message_id, total) — PIVOTE
    B-->>CA: ok, saldo_resultante
    CA->>CA: saga → debitada
    CA->>CAT: DescontarStock(message_id, items)
    CAT-->>CA: ok (stock -= n, reserva liberada)
    CA->>CA: TX local: vaciar carrito + DeliveryLog(pendiente_envio) + saga → completada
    CA-->>C: 201 {saga_id, total_cobrado, saldo_restante}

    Note over CA,D: Tramo ASINCRÓNICO post-pivote (no bloquea la respuesta)
    CA->>MQ: CrearDeliveriesCmd → cola delivery.crear_deliveries
    CA->>CA: DeliveryLog → enviado
    MQ->>D: consume
    D->>D: crear un DeliveryOrder por ítem (idempotente por message_id)
    D->>MQ: DeliveriesCreado → carrito.respuesta.<saga_id>
    MQ->>CA: confirmación por el canal propio de la saga
    CA->>CA: DeliveryLog → confirmado
```

## Camino de fallo: pivote rechazado → compensación

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant CA as Carrito (orquestador)
    participant CAT as Catálogo
    participant B as Billetera

    C->>CA: POST /carrito/checkout
    CA->>CAT: ReservarStock(items)
    CAT-->>CA: ok (reserva tomada)
    CA->>B: DebitarSaldo(total) — PIVOTE
    B-->>CA: ok=false "Saldo insuficiente"
    Note over CA,CAT: COMPENSACIÓN: devolver la reserva
    CA->>CAT: LiberarStock(items)
    CAT-->>CA: ok (stock_reservado -= n)
    CA->>CA: saga → compensada
    CA-->>C: 402 Payment Required
    Note over C,CA: El carrito NO se vació: el usuario puede cargar saldo y reintentar
```

## Broker caído: retry desde el log (outbox)

```mermaid
sequenceDiagram
    autonumber
    participant CA as Carrito (orquestador)
    participant LOG as delivery_log (BD Carrito)
    participant MQ as RabbitMQ
    participant D as Delivery

    Note over CA,LOG: El checkout ya respondió 201; el log quedó escrito en la misma TX
    CA--xMQ: publicar CrearDeliveriesCmd (broker caído)
    CA->>LOG: estado = pendiente_envio, intentos++
    loop Worker de retry (cada 30s)
        CA->>LOG: leer no-confirmados
        CA->>MQ: re-publicar con el MISMO message_id
        MQ->>D: consume
        D->>D: idempotente: si ya procesó ese message_id,<br/>devuelve los mismos delivery_ids sin duplicar
        D->>MQ: DeliveriesCreado → carrito.respuesta.<saga_id>
        MQ->>CA: confirmación
        CA->>LOG: estado = confirmado (el retry deja de levantarlo)
    end
```

## Estados

| Saga (`sagas_checkout`) | Log (`delivery_log`) |
|---|---|
| iniciada → stock_reservado → debitada → stock_descontado → **completada** | pendiente_envio → enviado → **confirmado** |
| iniciada → **fallida** (reserva rechazada, HTTP 409 — sin efectos) | |
| stock_reservado → **compensada** (pivote falló → LiberarStock, HTTP 402) | |
