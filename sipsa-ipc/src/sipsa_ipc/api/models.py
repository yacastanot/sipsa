"""Modelos Pydantic de respuesta para la API SIPSA IPC — F8."""
from __future__ import annotations

from pydantic import BaseModel, Field


class MesDisponible(BaseModel):
    mes: str = Field(..., examples=["Abril"])
    anio: int = Field(..., examples=[2025])
    periodo: str = Field(..., examples=["Abril2025"])


class ListaMesesResponse(BaseModel):
    periodos: list[MesDisponible]
    total: int


class AbastItem(BaseModel):
    departamento: str
    sum_ton: float = Field(..., description="Toneladas abastecidas")
    participacion_pct: float = Field(..., description="Participación % sobre total artículo")


class AbastecimientoResponse(BaseModel):
    periodo: str
    articulo_ipc: str
    codigo_ipc: int
    total_ton: float
    departamentos: list[AbastItem]


class DestinoItem(BaseModel):
    ciudad: str
    sum_ton: float
    participacion_pct: float


class DestinoResponse(BaseModel):
    periodo: str
    articulo_ipc: str
    codigo_ipc: int
    total_ton: float
    ciudades: list[DestinoItem]


class OtrosItem(BaseModel):
    pais: str
    sum_ton: float
    participacion_pct: float


class EstadisticasResponse(BaseModel):
    periodo: str
    articulo_ipc: str
    codigo_ipc: int
    abast_mes_actual: float
    abast_mes_anterior: float
    abast_anio_anterior: float
    variac_mensual_pct: float
    variac_anual_pct: float
    variac_mensual_fmt: str = Field(..., description="Formato colombiano: -3,15%")
    variac_anual_fmt: str
    top_departamentos: list[AbastItem]
    top_destinos: list[DestinoItem]
    importaciones: list[OtrosItem]


class ComparacionItem(BaseModel):
    articulo_ipc: str
    codigo_ipc: int
    abast_periodo_a: float
    abast_periodo_b: float
    variacion_pct: float


class ComparacionResponse(BaseModel):
    periodo_a: str
    periodo_b: str
    articulos: list[ComparacionItem]


class PipelineStatus(BaseModel):
    mes: str
    estado: str = Field(..., description="iniciado | completado | error")
    mensaje: str
    returncode: int | None = None
