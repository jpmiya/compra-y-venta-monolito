from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.firebase import verify_firebase_token

bearer_scheme = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    from app.service import get_usuario_by_firebase_uid, registrar_ultimo_acceso

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

    usuario = await get_usuario_by_firebase_uid(db, firebase_uid)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario no registrado en el sistema",
        )

    await registrar_ultimo_acceso(db, usuario)
    return usuario


async def get_current_active_user(current_user=Depends(get_current_user)):
    if current_user.estado != "activo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        )
    return current_user


async def get_verified_firebase_payload(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Solo valida el token de Firebase — a diferencia de get_current_user, no
    exige que ya exista un `usuario` local. Es el único punto de entrada sin
    ese requisito, para poder resolver el huevo-y-la-gallina del primer
    acceso (token válido pero sin registro local todavía)."""
    try:
        payload = verify_firebase_token(credentials.credentials)
        if not payload.get("uid"):
            raise ValueError("UID ausente en el token")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Firebase inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
