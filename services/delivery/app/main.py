import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.adapters.broker.consumer import RabbitMQConsumer


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    consumer_task = None
    if settings.BROKER_ENABLED:
        consumer_task = asyncio.create_task(RabbitMQConsumer().run())

    yield

    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass


from app.adapters.rest.router import router as public_router

app = FastAPI(
    title="Delivery",
    description="Microservicio de entregas — participante asincrónico post-pivote de la saga (CrearDeliveries vía RabbitMQ)",
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
