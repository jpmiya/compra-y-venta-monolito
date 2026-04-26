import re
import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, computed_field, field_validator

TASA_IMPUESTO = 0.14

TRANSICIONES_VALIDAS: dict[str, set[str]] = {
    "pendiente": {"pagada", "cancelada"},
    "pagada": {"procesando", "cancelada"},
    "procesando": {"enviada"},
    "enviada": {"entregada"},
    "entregada": set(),
    "cancelada": set(),
}

PHONE_RE = re.compile(r"^\+\d{1,3}\s?\d{6,14}$")


class CrearOrdenRequest(BaseModel):
    direccion_entrega: str
    telefono_contacto: str

    @field_validator("direccion_entrega")
    @classmethod
    def validate_direccion(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("La dirección de entrega no puede estar vacía")
        return v

    @field_validator("telefono_contacto")
    @classmethod
    def validate_telefono(cls, v: str) -> str:
        if not PHONE_RE.match(v):
            raise ValueError("Teléfono inválido, use formato internacional (ej: +54 9 1234 5678)")
        return v


class ActualizarEstadoRequest(BaseModel):
    estado: str
    numero_seguimiento: Optional[str] = None

    @field_validator("estado")
    @classmethod
    def validate_estado(cls, v: str) -> str:
        estados = set(TRANSICIONES_VALIDAS.keys())
        if v not in estados:
            raise ValueError(f"Estado inválido. Opciones: {', '.join(sorted(estados))}")
        return v


class OrdenItemResponse(BaseModel):
    producto_id: uuid.UUID
    nombre_producto: str
    cantidad: int
    precio_unitario: float

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def subtotal(self) -> float:
        return round(self.cantidad * self.precio_unitario, 2)


class OrdenResponse(BaseModel):
    id: uuid.UUID
    numero_orden: str
    usuario_id: uuid.UUID
    items: List[OrdenItemResponse]
    subtotal: float
    impuesto: float
    descuento: float
    total: float
    estado: str
    direccion_entrega: str
    telefono_contacto: str
    numero_seguimiento: Optional[str]
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    model_config = {"from_attributes": True}


class SeguimientoResponse(BaseModel):
    numero_orden: str
    estado: str
    numero_seguimiento: Optional[str]
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    model_config = {"from_attributes": True}
