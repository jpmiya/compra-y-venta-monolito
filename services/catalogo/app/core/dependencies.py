from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.firebase import verify_firebase_token
from app.core.http_client import IdentidadClient, get_identidad_client

bearer_scheme = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_usuario(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    identidad: IdentidadClient = Depends(get_identidad_client),
) -> dict:
    """Verifica Firebase token y resuelve el usuario (id + persona_id) llamando a Identidad.

    Catálogo necesita persona_id además del id para validar que la dirección
    del punto de venta pertenece al vendedor.
    """
    try:
        payload = verify_firebase_token(credentials.credentials)
        firebase_uid: str = payload.get("uid")
        if not firebase_uid:
            raise ValueError("UID ausente en el token")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Firebase inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    usuario = await identidad.get_usuario_by_firebase_uid(firebase_uid)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario no registrado en el sistema",
        )
    if usuario.get("estado") != "activo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        )
    return usuario
