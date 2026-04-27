from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./firebase-service-account.json"
    # Firebase web config (para el JS SDK en el navegador — no son secretos)
    FIREBASE_WEB_API_KEY: str = ""
    FIREBASE_AUTH_DOMAIN: str = ""
    # Billetera virtual
    BILLETERA_LIMITE_CARGA: float = 100000.0
    BILLETERA_MONEDA: str = "ARS"
    # Encriptación de datos sensibles (base64 de 32 bytes — generá con: python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
    ENCRYPTION_KEY: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
