from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


from app.adapters.rest.router import router as public_router
from app.adapters.rest.interno import router as interno_router

app = FastAPI(
    title="Billetera Virtual",
    description="Microservicio de billetera — pivote de la saga de checkout (DebitarSaldo)",
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
app.include_router(interno_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
