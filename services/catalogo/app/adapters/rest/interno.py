"""Endpoints internos — comandos de stock de la saga de checkout, idempotentes por message_id.

- ReservarStock: aparta stock disponible antes del pivote (compensable).
- DescontarStock: confirma la reserva después del pivote (DebitarSaldo ok).
- LiberarStock: compensación de ReservarStock cuando el pivote falla.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app import service
from app.adapters.rest.schemas import (
    ReservarStockCmd,
    DescontarStockCmd,
    LiberarStockCmd,
    StockRespuesta,
    ProductoResponse,
)

router = APIRouter(prefix="/interno", tags=["Interno"])


@router.post("/stock/reservar", response_model=StockRespuesta)
async def reservar_stock(cmd: ReservarStockCmd, db: AsyncSession = Depends(get_db)):
    """Todo-o-nada: si algún ítem no tiene stock disponible, no se reserva nada.
    Devuelve ok=False (no lanza excepción) para que el orquestador aborte la saga."""
    ok, error = await service.reservar_stock(db, cmd.message_id, cmd.items)
    return StockRespuesta(ok=ok, error=error)


@router.post("/stock/descontar", response_model=StockRespuesta)
async def descontar_stock(cmd: DescontarStockCmd, db: AsyncSession = Depends(get_db)):
    ok, error = await service.descontar_stock(db, cmd.message_id, cmd.items)
    return StockRespuesta(ok=ok, error=error)


@router.post("/stock/liberar", response_model=StockRespuesta)
async def liberar_stock(cmd: LiberarStockCmd, db: AsyncSession = Depends(get_db)):
    ok, error = await service.liberar_stock(db, cmd.message_id, cmd.items)
    return StockRespuesta(ok=ok, error=error)


@router.get("/productos/{producto_id}", response_model=ProductoResponse)
async def get_producto(producto_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Consulta interna de producto (la usarán Carrito y Delivery). Sin composición de dirección."""
    producto = await service.get_producto_by_id(db, producto_id)
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return producto
