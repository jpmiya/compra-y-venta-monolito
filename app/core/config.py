from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Base de datos
    DATABASE_URL: str
    # Firebase
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./firebase-service-account.json"
    FIREBASE_WEB_API_KEY: str = ""
    FIREBASE_AUTH_DOMAIN: str = ""
    FIREBASE_PROJECT_ID: str = ""
    # Seguridad
    SEGURIDAD_MAX_INTENTOS_LOGIN: int = 5
    SEGURIDAD_TIEMPO_SESION_MINUTOS: int = 60
    # Billetera virtual
    BILLETERA_LIMITE_CARGA: float = 100000.0
    BILLETERA_MONEDA: str = "ARS"
    # Búsqueda
    BUSQUEDA_MAX_RESULTADOS: int = 100
    # Notificaciones
    NOTIFICACIONES_EMAIL_HABILITADO: bool = False
    NOTIFICACIONES_EMAIL_REMITENTE: str = ""
    # Encriptación de datos sensibles (base64 de 32 bytes — generá con: python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
    ENCRYPTION_KEY: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
