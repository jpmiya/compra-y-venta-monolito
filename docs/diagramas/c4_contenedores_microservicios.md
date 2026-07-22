# C4 — Contenedores (arquitectura de microservicios)

Diagrama de contenedores del sistema migrado: 5 microservicios hexagonales con
database-per-service, un API Gateway como única puerta de entrada, y RabbitMQ
solo para el tramo asincrónico de la saga (CrearDeliveries).

```mermaid
flowchart TB
    cliente["Cliente<br/>(UI web / Postman / app)"]
    firebase["Firebase Authentication<br/>(externo)"]

    subgraph perimetro["Perímetro de microservicios (docker compose --profile microservices)"]
        gateway["API Gateway<br/>nginx :8080<br/>enruta por recurso, bloquea /interno/*"]

        subgraph identidad_svc["Identidad y Acceso :8001"]
            identidad["FastAPI hexagonal<br/>/personas /usuarios /direcciones"]
            identidad_db[("identidad_db<br/>PostgreSQL :5434")]
        end

        subgraph billetera_svc["Billetera :8002"]
            billetera["FastAPI hexagonal<br/>/billetera<br/>interno: DebitarSaldo (PIVOTE)"]
            billetera_db[("billetera_db<br/>PostgreSQL :5436")]
        end

        subgraph catalogo_svc["Catálogo :8003"]
            catalogo["FastAPI hexagonal<br/>/productos /busqueda<br/>interno: Reservar/Descontar/LiberarStock"]
            catalogo_db[("catalogo_db<br/>PostgreSQL :5438")]
        end

        subgraph delivery_svc["Delivery :8004"]
            delivery["FastAPI hexagonal<br/>/deliveries<br/>consumer: CrearDeliveries"]
            delivery_db[("delivery_db<br/>PostgreSQL :5440")]
        end

        subgraph carrito_svc["Carrito & Checkout :8005 — ORQUESTADOR"]
            carrito["FastAPI hexagonal<br/>/carrito /carrito/checkout<br/>CheckoutSaga + DeliveryLog (outbox)"]
            carrito_db[("carrito_db<br/>PostgreSQL :5442<br/>+ sagas_checkout + delivery_log")]
        end

        rabbit[["RabbitMQ :5672<br/>cola delivery.crear_deliveries<br/>+ carrito.respuesta.&lt;saga_id&gt; (una por saga)"]]
    end

    cliente -->|"HTTPS + Bearer (Firebase ID token)"| gateway
    cliente -.->|login| firebase

    gateway --> identidad
    gateway --> billetera
    gateway --> catalogo
    gateway --> delivery
    gateway --> carrito

    identidad --- identidad_db
    billetera --- billetera_db
    catalogo --- catalogo_db
    delivery --- delivery_db
    carrito --- carrito_db

    %% Auth: cada servicio valida el token y resuelve el usuario en Identidad
    billetera -.->|"REST interno<br/>usuario by firebase_uid"| identidad
    catalogo -.->|"REST interno<br/>usuario + direcciones (batch)"| identidad
    delivery -.->|"REST interno<br/>usuario by firebase_uid"| identidad
    carrito -.->|"REST interno<br/>usuario by firebase_uid"| identidad

    %% Saga sincrónica
    carrito -->|"ReservarStock / DescontarStock / LiberarStock<br/>(REST sync, idempotente)"| catalogo
    carrito -->|"DebitarSaldo (PIVOTE)<br/>(REST sync, idempotente)"| billetera
    carrito -->|"producto (precio, stock, punto de venta)"| catalogo

    %% Tramo async
    carrito ==>|"CrearDeliveriesCmd<br/>(async, outbox + retry)"| rabbit
    rabbit ==>|consume| delivery
    delivery ==>|"DeliveriesCreado<br/>(canal propio de la saga)"| rabbit
    rabbit ==>|confirmación| carrito
```

## Decisiones reflejadas

| Decisión | Dónde se ve |
|---|---|
| Database-per-service | 5 PostgreSQL independientes; FKs cross-service son UUID sin constraint |
| Gateway único | nginx :8080; `/interno/*` devuelve 403 desde afuera |
| Sync salvo delivery | Flechas sólidas = REST sincrónico; dobles = RabbitMQ |
| Pivote = DebitarSaldo | Billetera; si falla, Carrito compensa con LiberarStock |
| Canales de respuesta múltiples | Una cola `carrito.respuesta.<saga_id>` por saga, no una cola general |
| Outbox | `delivery_log` en la BD de Carrito, con worker de retry |

> El monolito original sigue en el repo (`app/`, puerto 8000) como base de comparación
> del TP y porque la UI web (Jinja2) y `notificaciones` quedaron fuera del alcance de
> la migración (plan §2).
