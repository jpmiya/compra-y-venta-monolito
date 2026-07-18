from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./firebase-service-account.json"
    IDENTIDAD_SERVICE_URL: str = "http://localhost:8001"
    BILLETERA_LIMITE_CARGA: float = 100000.0
    BILLETERA_MONEDA: str = "ARS"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
