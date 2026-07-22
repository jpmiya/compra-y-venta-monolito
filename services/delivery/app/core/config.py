from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./firebase-service-account.json"
    IDENTIDAD_SERVICE_URL: str = "http://localhost:8001"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    # Cola de comandos de la saga (el orquestador publica CrearDeliveriesCmd acá)
    COLA_CREAR_DELIVERIES: str = "delivery.crear_deliveries"
    # Permite apagar el consumer (tests / entornos sin broker)
    BROKER_ENABLED: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
