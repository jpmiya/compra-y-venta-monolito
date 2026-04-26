import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import Persona, Usuario, Direccion
from app.modules.admin.schemas import (
    PersonaCreate,
    PersonaUpdate,
    UsuarioCreate,
    UsuarioUpdate,
    DireccionCreate,
    DireccionUpdate,
)


# --- Persona ---

async def listar_personas(db: AsyncSession) -> List[Persona]:
    result = await db.execute(select(Persona).order_by(Persona.nombre_completo))
    return result.scalars().all()


async def get_persona_by_id(db: AsyncSession, persona_id: uuid.UUID) -> Optional[Persona]:
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    return result.scalar_one_or_none()


async def get_persona_by_documento(db: AsyncSession, documento: str) -> Optional[Persona]:
    result = await db.execute(
        select(Persona).where(Persona.documento_identidad == documento)
    )
    return result.scalar_one_or_none()


async def crear_persona(db: AsyncSession, data: PersonaCreate) -> Persona:
    persona = Persona(**data.model_dump())
    db.add(persona)
    await db.commit()
    await db.refresh(persona)
    return persona


async def actualizar_persona(
    db: AsyncSession, persona: Persona, data: PersonaUpdate
) -> Persona:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(persona, field, value)
    await db.commit()
    await db.refresh(persona)
    return persona


async def eliminar_persona(db: AsyncSession, persona: Persona) -> None:
    persona.estado = "inactivo"
    await db.commit()


# --- Usuario ---

async def get_usuario_by_id(db: AsyncSession, usuario_id: uuid.UUID) -> Optional[Usuario]:
    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    return result.scalar_one_or_none()


async def get_usuario_by_firebase_uid(
    db: AsyncSession, firebase_uid: str
) -> Optional[Usuario]:
    result = await db.execute(
        select(Usuario).where(Usuario.firebase_uid == firebase_uid)
    )
    return result.scalar_one_or_none()


async def get_usuario_by_email(db: AsyncSession, email: str) -> Optional[Usuario]:
    result = await db.execute(select(Usuario).where(Usuario.email == email))
    return result.scalar_one_or_none()


async def listar_usuarios_de_persona(
    db: AsyncSession, persona_id: uuid.UUID
) -> List[Usuario]:
    result = await db.execute(
        select(Usuario).where(Usuario.persona_id == persona_id)
    )
    return result.scalars().all()


async def crear_usuario(
    db: AsyncSession, persona_id: uuid.UUID, data: UsuarioCreate
) -> Usuario:
    usuario = Usuario(persona_id=persona_id, **data.model_dump())
    db.add(usuario)
    await db.commit()
    await db.refresh(usuario)
    return usuario


async def actualizar_usuario(
    db: AsyncSession, usuario: Usuario, data: UsuarioUpdate
) -> Usuario:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(usuario, field, value)
    await db.commit()
    await db.refresh(usuario)
    return usuario


async def eliminar_usuario(db: AsyncSession, usuario: Usuario) -> None:
    usuario.estado = "inactivo"
    await db.commit()


async def registrar_ultimo_acceso(db: AsyncSession, usuario: Usuario) -> None:
    usuario.fecha_ultimo_acceso = datetime.now(timezone.utc)
    await db.commit()


# --- Dirección ---

async def listar_direcciones_de_persona(
    db: AsyncSession, persona_id: uuid.UUID
) -> List[Direccion]:
    result = await db.execute(
        select(Direccion).where(
            Direccion.persona_id == persona_id,
            Direccion.activa == True,
        )
    )
    return result.scalars().all()


async def get_direccion_by_id(
    db: AsyncSession, direccion_id: uuid.UUID
) -> Optional[Direccion]:
    result = await db.execute(select(Direccion).where(Direccion.id == direccion_id))
    return result.scalar_one_or_none()


async def crear_direccion(
    db: AsyncSession, persona_id: uuid.UUID, data: DireccionCreate
) -> Direccion:
    direccion = Direccion(persona_id=persona_id, **data.model_dump())
    db.add(direccion)
    await db.commit()
    await db.refresh(direccion)
    return direccion


async def actualizar_direccion(
    db: AsyncSession, direccion: Direccion, data: DireccionUpdate
) -> Direccion:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(direccion, field, value)
    await db.commit()
    await db.refresh(direccion)
    return direccion


async def eliminar_direccion(db: AsyncSession, direccion: Direccion) -> None:
    direccion.activa = False
    await db.commit()
