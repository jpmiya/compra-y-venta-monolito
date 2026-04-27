import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, field_validator


class DireccionPuntoVentaResponse(BaseModel):
    id: uuid.UUID
    calle: str
    numero: str
    ciudad: str
    provincia: str
    descripcion: Optional[str]

    model_config = {"from_attributes": True}


class CategoriaResponse(BaseModel):
    id: uuid.UUID
    nombre: str
    descripcion: Optional[str]
    imagen: Optional[str]

    model_config = {"from_attributes": True}


class ProductoCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    precio: float
    categoria_id: uuid.UUID
    stock: int
    sku: str
    imagenes: List[str]
    direccion_punto_venta_id: uuid.UUID

    @field_validator("nombre")
    @classmethod
    def validate_nombre(cls, v: str) -> str:
        if len(v) < 5:
            raise ValueError("El nombre debe tener al menos 5 caracteres")
        if len(v) > 255:
            raise ValueError("El nombre no puede superar los 255 caracteres")
        return v

    @field_validator("precio")
    @classmethod
    def validate_precio(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("El precio debe ser positivo")
        return v

    @field_validator("stock")
    @classmethod
    def validate_stock(cls, v: int) -> int:
        if v < 0:
            raise ValueError("El stock no puede ser negativo")
        return v

    @field_validator("imagenes")
    @classmethod
    def validate_imagenes(cls, v: List[str]) -> List[str]:
        if len(v) < 1:
            raise ValueError("Se requiere al menos una imagen")
        if len(v) > 10:
            raise ValueError("No se pueden cargar más de 10 imágenes")
        return v


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    precio: Optional[float] = None
    categoria_id: Optional[uuid.UUID] = None
    stock: Optional[int] = None
    imagenes: Optional[List[str]] = None
    activo: Optional[bool] = None
    direccion_punto_venta_id: Optional[uuid.UUID] = None

    @field_validator("precio")
    @classmethod
    def validate_precio(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("El precio debe ser positivo")
        return v

    @field_validator("stock")
    @classmethod
    def validate_stock(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("El stock no puede ser negativo")
        return v

    @field_validator("imagenes")
    @classmethod
    def validate_imagenes(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            if len(v) < 1:
                raise ValueError("Se requiere al menos una imagen")
            if len(v) > 10:
                raise ValueError("No se pueden cargar más de 10 imágenes")
        return v


class ProductoResponse(BaseModel):
    id: uuid.UUID
    nombre: str
    descripcion: Optional[str]
    precio: float
    categoria_id: uuid.UUID
    stock: int
    sku: str
    imagenes: List[str]
    vendedor_id: uuid.UUID
    direccion_punto_venta_id: uuid.UUID
    direccion_punto_venta: Optional[DireccionPuntoVentaResponse] = None
    activo: bool
    calificacion_promedio: float
    fecha_creacion: datetime

    model_config = {"from_attributes": True}


class ProductoListResponse(BaseModel):
    items: List[ProductoResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ResenaCreate(BaseModel):
    calificacion: int
    comentario: Optional[str] = None

    @field_validator("calificacion")
    @classmethod
    def validate_calificacion(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("La calificación debe estar entre 1 y 5")
        return v
