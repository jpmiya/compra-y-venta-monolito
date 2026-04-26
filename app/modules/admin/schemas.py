import uuid
from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


# --- Persona ---

class PersonaCreate(BaseModel):
    nombre_completo: str
    documento_identidad: str
    telefono: Optional[str] = None
    fecha_nacimiento: Optional[date] = None

    @field_validator("nombre_completo", "documento_identidad")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Este campo no puede estar vacío")
        return v


class PersonaUpdate(BaseModel):
    nombre_completo: Optional[str] = None
    telefono: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    estado: Optional[str] = None

    @field_validator("estado")
    @classmethod
    def validate_estado(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ("activo", "inactivo"):
            raise ValueError("Estado debe ser 'activo' o 'inactivo'")
        return v


class PersonaResponse(BaseModel):
    id: uuid.UUID
    nombre_completo: str
    documento_identidad: str
    telefono: Optional[str]
    fecha_nacimiento: Optional[date]
    fecha_registro: datetime
    estado: str

    model_config = {"from_attributes": True}


# --- Usuario ---

class UsuarioCreate(BaseModel):
    email: EmailStr
    firebase_uid: str

    @field_validator("firebase_uid")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El Firebase UID no puede estar vacío")
        return v


class UsuarioUpdate(BaseModel):
    email: Optional[EmailStr] = None
    estado: Optional[str] = None

    @field_validator("estado")
    @classmethod
    def validate_estado(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ("activo", "inactivo"):
            raise ValueError("Estado debe ser 'activo' o 'inactivo'")
        return v


class UsuarioResponse(BaseModel):
    id: uuid.UUID
    persona_id: uuid.UUID
    email: str
    firebase_uid: str
    fecha_ultimo_acceso: Optional[datetime]
    estado: str

    model_config = {"from_attributes": True}


# --- Dirección ---

class DireccionCreate(BaseModel):
    calle: str
    numero: str
    ciudad: str
    provincia: str
    descripcion: Optional[str] = None

    @field_validator("calle", "numero", "ciudad", "provincia")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Este campo no puede estar vacío")
        return v


class DireccionUpdate(BaseModel):
    calle: Optional[str] = None
    numero: Optional[str] = None
    ciudad: Optional[str] = None
    provincia: Optional[str] = None
    descripcion: Optional[str] = None
    activa: Optional[bool] = None


class DireccionResponse(BaseModel):
    id: uuid.UUID
    persona_id: uuid.UUID
    calle: str
    numero: str
    ciudad: str
    provincia: str
    descripcion: Optional[str]
    activa: bool

    model_config = {"from_attributes": True}
