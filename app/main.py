from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.admin.router import router as admin_router
from app.web.router import router as web_router
from app.modules.busqueda.router import router as busqueda_router
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

app.include_router(web_router)
app.include_router(admin_router)
app.include_router(productos_router)
app.include_router(carrito_router)
app.include_router(ordenes_router)
app.include_router(busqueda_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
