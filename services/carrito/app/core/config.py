from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./firebase-service-account.json"
    IDENTIDAD_SERVICE_URL: str = "http://localhost:8001"
    BILLETERA_SERVICE_URL: str = "http://localhost:8002"
    CATALOGO_SERVICE_URL: str = "http://localhost:8003"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    COLA_CREAR_DELIVERIES: str = "delivery.crear_deliveries"
    # Prefijo de los canales de respuesta (uno por saga): carrito.respuesta.<saga_id>
    REPLY_QUEUE_PREFIX: str = "carrito.respuesta"
    # Permite apagar el broker (tests / entornos sin RabbitMQ)
    BROKER_ENABLED: bool = True
    # Intervalo del worker de retry del log de deliverys (segundos)
    DELIVERY_RETRY_INTERVALO: float = 30.0
    CARRITO_MONEDA: str = "ARS"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
