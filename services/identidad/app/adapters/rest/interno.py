"""Endpoints internos — solo accesibles desde la red interna de microservicios (sin auth pública)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app import service
from app.adapters.rest.schemas import UsuarioResponse, DireccionResponse

router = APIRouter(prefix="/interno", tags=["Interno"])


@router.get("/usuarios/{usuario_id}", response_model=UsuarioResponse)
async def get_usuario(
    usuario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    usuario = await service.get_usuario_by_id(db, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return usuario


@router.get("/usuarios/by-firebase/{firebase_uid}", response_model=UsuarioResponse)
async def get_usuario_by_firebase(
    firebase_uid: str,
    db: AsyncSession = Depends(get_db),
):
    usuario = await service.get_usuario_by_firebase_uid(db, firebase_uid)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return usuario


@router.get("/direcciones", response_model=list[DireccionResponse])
async def get_direcciones_batch(
    ids: list[uuid.UUID] = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Resolución batch de direcciones (composición síncrona desde Catálogo)."""
    return await service.get_direcciones_by_ids(db, ids)


@router.get("/direcciones/{direccion_id}", response_model=DireccionResponse)
async def get_direccion(
    direccion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    direccion = await service.get_direccion_by_id(db, direccion_id)
    if not direccion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dirección no encontrada"
        )
    return direccion
