import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_active_user
from app.modules.admin import service
from app.modules.admin.schemas import (
    DireccionCreate,
    DireccionResponse,
    DireccionUpdate,
    PersonaCreate,
    PersonaResponse,
    PersonaUpdate,
    UsuarioCreate,
    UsuarioResponse,
    UsuarioUpdate,
)

router = APIRouter(tags=["Administración"])


# --- Personas ---

@router.get("/personas", response_model=list[PersonaResponse])
async def listar_personas(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.listar_personas(db)


@router.post("/personas", response_model=PersonaResponse, status_code=status.HTTP_201_CREATED)
async def crear_persona(
    data: PersonaCreate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if await service.get_persona_by_documento(db, data.documento_identidad):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una persona con ese documento de identidad",
        )
    return await service.crear_persona(db, data)


@router.get("/personas/{persona_id}", response_model=PersonaResponse)
async def obtener_persona(
    persona_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    persona = await service.get_persona_by_id(db, persona_id)
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona no encontrada")
    return persona


@router.put("/personas/{persona_id}", response_model=PersonaResponse)
async def actualizar_persona(
    persona_id: uuid.UUID,
    data: PersonaUpdate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    persona = await service.get_persona_by_id(db, persona_id)
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona no encontrada")
    return await service.actualizar_persona(db, persona, data)


@router.delete("/personas/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_persona(
    persona_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    persona = await service.get_persona_by_id(db, persona_id)
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona no encontrada")
    await service.eliminar_persona(db, persona)


# --- Usuarios de Persona ---

@router.get("/personas/{persona_id}/usuarios", response_model=list[UsuarioResponse])
async def listar_usuarios_de_persona(
    persona_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not await service.get_persona_by_id(db, persona_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona no encontrada")
    return await service.listar_usuarios_de_persona(db, persona_id)


@router.post(
    "/personas/{persona_id}/usuarios",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_usuario(
    persona_id: uuid.UUID,
    data: UsuarioCreate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not await service.get_persona_by_id(db, persona_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona no encontrada")
    if await service.get_usuario_by_email(db, data.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ya registrado")
    if await service.get_usuario_by_firebase_uid(db, data.firebase_uid):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Firebase UID ya registrado"
        )
    return await service.crear_usuario(db, persona_id, data)


@router.put("/usuarios/{usuario_id}", response_model=UsuarioResponse)
async def actualizar_usuario(
    usuario_id: uuid.UUID,
    data: UsuarioUpdate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    usuario = await service.get_usuario_by_id(db, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return await service.actualizar_usuario(db, usuario, data)


@router.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_usuario(
    usuario_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    usuario = await service.get_usuario_by_id(db, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    await service.eliminar_usuario(db, usuario)


# --- Direcciones ---

@router.get("/personas/{persona_id}/direcciones", response_model=list[DireccionResponse])
async def listar_direcciones(
    persona_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not await service.get_persona_by_id(db, persona_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona no encontrada")
    return await service.listar_direcciones_de_persona(db, persona_id)


@router.post(
    "/personas/{persona_id}/direcciones",
    response_model=DireccionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_direccion(
    persona_id: uuid.UUID,
    data: DireccionCreate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not await service.get_persona_by_id(db, persona_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona no encontrada")
    return await service.crear_direccion(db, persona_id, data)


@router.put("/direcciones/{direccion_id}", response_model=DireccionResponse)
async def actualizar_direccion(
    direccion_id: uuid.UUID,
    data: DireccionUpdate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    direccion = await service.get_direccion_by_id(db, direccion_id)
    if not direccion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dirección no encontrada"
        )
    return await service.actualizar_direccion(db, direccion, data)


@router.delete("/direcciones/{direccion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_direccion(
    direccion_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    direccion = await service.get_direccion_by_id(db, direccion_id)
    if not direccion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dirección no encontrada"
        )
    await service.eliminar_direccion(db, direccion)
