"""Schemas pandera para la capa Raw/Bronze del pipeline SIPSA IPC.

Replica las validaciones implícitas del programa SAS:
  SIPSA_A_MODELO_IPC.sas — sección PROC IMPORT y data step IPC1.

La validación es lazy=True para exponer todas las violaciones de una vez.
"""
from __future__ import annotations

import pandera.pandas as pa

# ─── Columnas requeridas ───────────────────────────────────────────────────────
# Tal como aparecen en el Excel de entrada BASE SIPSA_A (18 columnas reales).
# Columnas con espacios y puntos se declaran con la clave exacta del DataFrame.
COLUMNAS_REQUERIDAS = {
    "Fuente",
    "FechaEncuesta",
    "Ali",
    "Cant Kg",
    "Departamento Proc.",
    "Municipio Proc.",
}

# ─── Schema de la capa Bronze ─────────────────────────────────────────────────
# strict=False → columnas adicionales del Excel son bienvenidas.
# coerce=False → los tipos ya vienen correctos desde catalog.yml (dtype forzado).
SCHEMA_RAW = pa.DataFrameSchema(
    columns={
        # Fuente: "Ciudad, Central de acopio"  ej: "Armenia, Mercar"
        "Fuente": pa.Column(
            str,
            nullable=False,
            description="Fuente en formato 'Ciudad, Central'",
        ),
        # FechaEncuesta: datetime64[ns] — sin nulos en el archivo de entrada real
        "FechaEncuesta": pa.Column(
            "datetime64[ns]",
            nullable=False,
            description="Fecha de la encuesta de campo",
        ),
        # Ali: variedad del alimento — ej: "Cebolla cabezona blanca"
        "Ali": pa.Column(
            str,
            nullable=False,
            description="Variedad del alimento (60+ opciones mapeables a 29 artículos IPC)",
        ),
        # Cant Kg: cantidad en kilogramos — siempre >= 0
        "Cant Kg": pa.Column(
            float,
            checks=pa.Check.ge(0),
            nullable=True,
            coerce=True,
            description="Cantidad registrada en kilogramos",
        ),
        # Departamento Proc.: departamento de procedencia del producto
        "Departamento Proc.": pa.Column(
            str,
            nullable=False,
            description="Departamento de procedencia (mayúsculas en el Excel)",
        ),
        # Municipio Proc.: municipio de procedencia
        "Municipio Proc.": pa.Column(
            str,
            nullable=False,
            description="Municipio de procedencia (mayúsculas en el Excel)",
        ),
        # Observaciones: campo mixto (texto libre + valores numéricos ocasionales)
        # En el Excel real puede contener strings, números y nulos → dtype=object
        "Observaciones": pa.Column(
            object,
            nullable=True,
            description="Observaciones del encuestador (texto libre, mixto)",
        ),
    },
    strict=False,   # Permite las 11 columnas adicionales del Excel
    coerce=False,   # No coerce — catalog.yml ya fijó los tipos
    name="BaseSIPSAIpcRaw",
)
