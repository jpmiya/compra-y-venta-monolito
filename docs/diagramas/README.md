# Diagramas del Sistema

## Arquitectura de microservicios (migración)

| Diagrama | Descripción |
|----------|-------------|
| [Contenedores — Microservicios](c4_contenedores_microservicios.md) | Los 5 servicios hexagonales, gateway nginx, RabbitMQ y database-per-service |
| [Secuencia: CheckoutSaga](uml_secuencia_checkout_saga.md) | Saga por orquestación: camino feliz, compensación (LiberarStock) y retry desde el log (outbox) |

## Modelo C4 (monolito — TP1)

| Diagrama | Descripción |
|----------|-------------|
| [Contexto](c4_contexto.md) | El sistema en relación con los usuarios y Firebase Authentication |
| [Contenedores](c4_contenedores.md) | API FastAPI, PostgreSQL y Firebase como contenedores |
| [Componentes](c4_componentes.md) | Módulos internos de la API y sus relaciones |

## Diagramas UML

| Diagrama | Descripción |
|----------|-------------|
| [Modelo de Datos](uml_modelo_datos.md) | Entidades del sistema y sus relaciones |
| [Secuencia: Compra](uml_secuencia_compra.md) | Flujo completo desde búsqueda hasta checkout |
| [Secuencia: Entrega](uml_secuencia_entrega.md) | Flujo desde visualización de pedidos hasta entrega |
