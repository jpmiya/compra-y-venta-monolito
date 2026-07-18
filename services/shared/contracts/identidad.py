"""Contratos de Identidad y Acceso para comunicación inter-servicio (REST síncrono)."""
import uuid
from typing import Optional
from pydantic import BaseModel


class UsuarioDTO(BaseModel):
    id: uuid.UUID
    persona_id: uuid.UUID
    email: str
    firebase_uid: str
    estado: str


class DireccionDTO(BaseModel):
    id: uuid.UUID
    persona_id: uuid.UUID
    calle: str
    numero: str
    ciudad: str
    provincia: str
    descripcion: Optional[str]
    activa: bool
