from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./firebase-service-account.json"
    # Firebase web config (para el JS SDK en el navegador — no son secretos)
    FIREBASE_WEB_API_KEY: str = ""
    FIREBASE_AUTH_DOMAIN: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
