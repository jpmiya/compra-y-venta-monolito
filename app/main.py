import logging
import time
from typing import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("app")


class LoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.time()
        status_code = 500

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        duration = round((time.time() - start) * 1000)
        logger.info(
            "%s %s → %s (%dms)",
            scope.get("method", ""),
            scope.get("path", ""),
            status_code,
            duration,
        )

from app.modules.admin.router import router as admin_router
from app.web.router import router as web_router
from app.modules.billetera.router import router as billetera_router
from app.modules.busqueda.router import router as busqueda_router
from app.modules.delivery.router import router as delivery_router
from app.modules.carrito.router import router as carrito_router
from app.modules.ordenes.router import router as ordenes_router
from app.modules.productos.router import router as productos_router

app = FastAPI(
    title="Compra y Venta API",
    description="Sistema monolítico de compra y venta",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)

app.include_router(admin_router)
app.include_router(web_router)
app.include_router(productos_router)
app.include_router(billetera_router)
app.include_router(delivery_router)
app.include_router(carrito_router)
app.include_router(ordenes_router)
app.include_router(busqueda_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
