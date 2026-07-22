import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base, AsyncSessionLocal

logger = logging.getLogger(__name__)


async def _worker_retry_deliveries():
    """Reenvía periódicamente los CrearDeliveries no confirmados del log (outbox).
    Reenviar es seguro: Delivery es idempotente por message_id."""
    from app.adapters.broker.publisher import get_publicador
    from app import saga as saga_module

    publicador = get_publicador()
    while True:
        await asyncio.sleep(settings.DELIVERY_RETRY_INTERVALO)
        try:
            async with AsyncSessionLocal() as db:
                reenviados = await saga_module.reintentar_deliveries_pendientes(db, publicador)
                if reenviados:
                    logger.info("Retry de deliverys: %d reenviado(s)", reenviados)
        except Exception:
            logger.exception("Worker de retry falló; sigue en el próximo ciclo")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    retry_task = None
    if settings.BROKER_ENABLED:
        retry_task = asyncio.create_task(_worker_retry_deliveries())

    yield

    if retry_task:
        retry_task.cancel()
        try:
            await retry_task
        except asyncio.CancelledError:
            pass


from app.adapters.rest.router import router as public_router

app = FastAPI(
    title="Carrito & Checkout",
    description="Microservicio orquestador de la CheckoutSaga (ReservarStock → DebitarSaldo → DescontarStock → CrearDeliveries async) con log de deliverys (outbox + retry)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
