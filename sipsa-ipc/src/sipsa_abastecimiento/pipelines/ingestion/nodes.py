"""Nodos del pipeline de ingesta — FASE 1: Capa de Ingesta de Datos.

SAS equivalente:
  proc import datafile="&entrada./&archivo." dbms=xlsx out=IPC replace;
    sheet="BASE SIPSA_A"; getnames=yes;
  run;

Flujo F1:
  params:archivo_entrada ──► [leer_base] ──► base_sipsa_bronze

El archivo Excel contiene los 3 períodos embebidos:
  - Mes actual       (ej: Abril 2025)
  - Mes anterior     (ej: Marzo 2025)
  - Año anterior     (ej: Abril 2024)

La columna PerFecha se asigna en F2 (Pipeline de Limpieza).
"""
from __future__ import annotations

import logging

import pandas as pd

from sipsa_abastecimiento.validations.schemas import COLUMNAS_REQUERIDAS, SCHEMA_RAW

log = logging.getLogger(__name__)

# Tipos forzados al leer el Excel — equivale al GETNAMES=YES de SAS
# más la especificación de tipos numéricos vs. texto.
# Todas las columnas de texto se fuerzan a str para evitar tipos mixtos
# (pandas/Excel puede retornar int en celdas que deberían ser str).
_DTYPE_EXCEL = {
    "Fuente":               str,
    "HoraEncuesta":         str,   # openpyxl devuelve datetime.time — forzar str
    "TipoVehiculo":         str,   # puede tener valores numéricos ocasionales
    "PlacaVehiculo":        str,
    "Cod. Depto Proc.":     str,   # Evita que Excel los interprete como float
    "Departamento Proc.":   str,
    "Cod. Municipio Proc.": str,   # Ej: '15638 quedaría como 15638.0 sin esto
    "Municipio Proc.":      str,
    "Observaciones":        str,   # Campo mixto: texto + números ocasionales
    "Grupo":                str,
    "Codigo CPC":           str,   # Ej: '0125301 → notación científica sin esto
    "Ali":                  str,
    "Pres":                 str,
    "Digitador":            str,
}

# Variantes de nombres de columna que llegan según la fuente del archivo.
# El GIT de SIPSA usa distintos encabezados según el período; se normalizan
# al estándar del pipeline antes de la validación de esquema.
_VARIANTES_COLUMNAS = {
    "Divipola Depto Proc.":                      "Cod. Depto Proc.",
    "Departamento":                              "Departamento Proc.",
    "Divipola Municipio / ISO 3166-1 País Proc.": "Cod. Municipio Proc.",
    "Municipio de Colombia / País Proc.":        "Municipio Proc.",
}


def leer_base(archivo_entrada: str) -> pd.DataFrame:
    """Lee el Excel mensual de entrada, valida columnas y aplica schema pandera.

    Equivalente SAS: el PROC IMPORT garantizaba implícitamente que todas las
    columnas del Excel estuvieran presentes. Este nodo replica ese contrato.

    Args:
        archivo_entrada: Ruta relativa al proyecto del archivo Excel.
                         Ej: "data/01_raw/Base_sipsa_abastecimiento_abr2025.xlsx"

    Returns:
        DataFrame con las 18 columnas de BASE SIPSA_A, listo para F2.

    Raises:
        FileNotFoundError: si el archivo no existe en la ruta indicada.
        ValueError: si faltan columnas requeridas en el Excel.
        pandera.errors.SchemaErrors: si alguna columna viola el schema.
    """
    log.info("Leyendo archivo de entrada: %s", archivo_entrada)

    df_raw = pd.read_excel(
        archivo_entrada,
        sheet_name="BASE SIPSA_A",
        header=0,
        dtype=_DTYPE_EXCEL,
    )

    log.info("Excel leído | filas=%d | columnas=%d", len(df_raw), len(df_raw.columns))

    # 1. Normalizar variantes de nombres de columna antes de validar
    _normalizar_columnas(df_raw)

    # 2. Verificación temprana de columnas — mensaje claro antes de pandera
    _verificar_columnas(df_raw)

    # 2. Schema pandera — lazy=True expone todas las violaciones de una vez
    validated = SCHEMA_RAW.validate(df_raw, lazy=True)

    n_meses = df_raw["FechaEncuesta"].dt.to_period("M").nunique()
    log.info(
        "leer_base OK | filas=%d | columnas=%d | períodos_distintos=%d",
        len(validated),
        len(validated.columns),
        n_meses,
    )
    return validated


# ─── helpers privados ────────────────────────────────────────────────────────

def _normalizar_columnas(df: pd.DataFrame) -> None:
    """Renombra in-place columnas que llegan con nombres variantes según la fuente."""
    renombres = {k: v for k, v in _VARIANTES_COLUMNAS.items() if k in df.columns}
    if renombres:
        df.rename(columns=renombres, inplace=True)
        log.info("Columnas renombradas: %s", renombres)


def _verificar_columnas(df: pd.DataFrame) -> None:
    """Lanza ValueError si el Excel no tiene todas las columnas requeridas."""
    faltantes = COLUMNAS_REQUERIDAS - set(df.columns)
    if faltantes:
        raise ValueError(
            f"El archivo Excel no tiene las columnas requeridas: {sorted(faltantes)}. "
            f"Columnas presentes: {sorted(df.columns.tolist())}"
        )
