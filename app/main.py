import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("app")

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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000)
    logger.info("%s %s → %s (%dms)", request.method, request.url.path, response.status_code, duration)
    return response

app.include_router(web_router)
app.include_router(admin_router)
app.include_router(productos_router)
app.include_router(billetera_router)
app.include_router(delivery_router)
app.include_router(carrito_router)
app.include_router(ordenes_router)
app.include_router(busqueda_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
