import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.dependencies import get_db, get_current_usuario_id
from app.core.http_client import (
    CatalogoClient,
    BilleteraClient,
    get_catalogo_client,
    get_billetera_client,
)
from app.adapters.broker.publisher import get_publicador
from app.adapters.persistence.models import DeliveryLog
from app import service, saga as saga_module
from app.saga import (
    CarritoVacioError,
    StockError,
    SaldoInsuficienteError,
)
from app.adapters.rest.schemas import (
    AgregarItemRequest,
    ModificarCantidadRequest,
    AplicarDescuentoRequest,
    CarritoResponse,
    CheckoutRequest,
    CheckoutResponse,
    SagaResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/carrito", tags=["Carrito & Checkout"])


@router.get("", response_model=CarritoResponse)
async def obtener_carrito(
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
):
    carrito = await service.get_or_create_carrito(db, usuario_id)
    return service.calcular_totales(carrito)


@router.post("/items", response_model=CarritoResponse, status_code=status.HTTP_201_CREATED)
async def agregar_item(
    data: AgregarItemRequest,
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
    catalogo: CatalogoClient = Depends(get_catalogo_client),
):
    try:
        carrito = await service.agregar_item(db, catalogo, usuario_id, data.producto_id, data.cantidad)
        return service.calcular_totales(carrito)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/items/{producto_id}", response_model=CarritoResponse)
async def modificar_cantidad(
    producto_id: uuid.UUID,
    data: ModificarCantidadRequest,
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
    catalogo: CatalogoClient = Depends(get_catalogo_client),
):
    try:
        carrito = await service.modificar_cantidad(
            db, catalogo, usuario_id, producto_id, data.cantidad
        )
        return service.calcular_totales(carrito)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/items/{producto_id}", response_model=CarritoResponse)
async def eliminar_item(
    producto_id: uuid.UUID,
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        carrito = await service.eliminar_item(db, usuario_id, producto_id)
        return service.calcular_totales(carrito)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def vaciar_carrito(
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
):
    await service.vaciar_carrito(db, usuario_id)


@router.post("/descuento", response_model=CarritoResponse)
async def aplicar_descuento(
    data: AplicarDescuentoRequest,
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        carrito = await service.aplicar_descuento(db, usuario_id, data.codigo)
        return service.calcular_totales(carrito)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/descuento", response_model=CarritoResponse)
async def remover_descuento(
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
):
    carrito = await service.remover_descuento(db, usuario_id)
    return service.calcular_totales(carrito)


@router.post("/checkout", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
async def checkout(
    data: CheckoutRequest,
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
    catalogo: CatalogoClient = Depends(get_catalogo_client),
    billetera: BilleteraClient = Depends(get_billetera_client),
):
    """Orquesta la CheckoutSaga. Errores:
    - 400: carrito vacío / producto inválido
    - 409: stock insuficiente (ReservarStock rechazado)
    - 402: saldo insuficiente (pivote falló → stock compensado con LiberarStock)
    """
    try:
        resultado = await saga_module.ejecutar_checkout(
            db, catalogo, billetera, usuario_id, data.direccion_entrega
        )
    except CarritoVacioError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except StockError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except SaldoInsuficienteError as e:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(e))

    # Tramo async post-pivote: publicar el CrearDeliveries del log (outbox).
    # Si falla, el worker de retry lo reintenta — el checkout ya está completado.
    if settings.BROKER_ENABLED:
        publicador = get_publicador()
        await saga_module.publicar_delivery_pendiente(db, publicador, resultado["saga_id"])
        asyncio.create_task(saga_module.escuchar_confirmacion(publicador, resultado["saga_id"]))

    return resultado


@router.get("/checkout/{saga_id}", response_model=SagaResponse)
async def estado_saga(
    saga_id: uuid.UUID,
    usuario_id: uuid.UUID = Depends(get_current_usuario_id),
    db: AsyncSession = Depends(get_db),
):
    saga = await saga_module.get_saga(db, saga_id)
    if not saga or saga.usuario_id != usuario_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saga no encontrada")
    respuesta = SagaResponse.model_validate(saga)
    log_result = await db.execute(select(DeliveryLog).where(DeliveryLog.saga_id == saga_id))
    log = log_result.scalar_one_or_none()
    if log:
        respuesta.delivery_estado = log.estado
    return respuesta
