"""Utilidades compartidas entre todos los pipelines del proyecto EMCES.

Funciones de normalización, lectura de Excel y validación de esquema.
Importar desde aquí evita duplicar estas definiciones en cada pipeline.
"""
from __future__ import annotations

import logging
import os
import re
import unicodedata

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Schema canónico de Registros Administrativos ─────────────────────────────
# Superset de ORDEN_FINAL de todos los sub-procesos RA (Fletes, Cancillería, Viajes...).
# Toda fuente RA debe poder proyectarse sobre este schema antes de consolidar.
# Columnas que una fuente no produce quedan como cadena vacía "".
ORDEN_FINAL_RA: list[str] = [
    "flujo_comercial", "idnoremp", "periodo", "mes", "periodo_mes",
    "sede", "csede",
    "idact", "idtipodo", "idnitcc", "iddv",
    "razsoc", "nombre", "sigla", "direccion",
    "idmpio", "nom_mpio", "iddepto", "nom_depto",
    "telefono", "ext", "celular", "filial",
    "rep_legal", "celular_rep_legal", "telefono_rep_legal", "ext_rep_legal",
    "idmail_rep_legal", "idmail_rep_legalconf",
    "contacto", "cargo",
    "idtel2", "idtel3", "idtelext2", "idcel_2", "idcel_3",
    "idmail3", "idmail3conf", "idmail4", "idmail4conf",
    "agrupacion", "descripcion_grupo", "codigo", "descripcion_cabps",
    "cpc", "descripcion_cpc", "nombre_departamento", "departamento",
    "pais", "nombre_pais", "pais_cod_iso_3166", "pais_cod_alpha_3",
    "acuerdo_1", "acuerdo_2", "acuerdo_3",
    "vrocefats", "vroce", "construccion",
    "total_en_miles_de_pesos", "trm_base", "total_en_dolares",
    "total_vrocefats_dolares", "total_vroce_dolares", "total_construccion_dolares",
    "modo", "descripcion_modo",
    "observacion", "id", "nom_estado", "novedad", "ociser",
    "justificacion_critico", "justificacion_logistico", "justificacion_supervisor",
]


# Columnas de ORDEN_FINAL_RA que deben permanecer numéricas (float64) en parquet.
# Todas las demás se normalizan a str para evitar tipos mixtos al concatenar fuentes.
_COLS_NUMERICAS_RA: frozenset[str] = frozenset({
    "total_en_dolares", "total_en_miles_de_pesos", "trm_base",
    "vrocefats", "vroce", "construccion",
    "total_vrocefats_dolares", "total_vroce_dolares", "total_construccion_dolares",
})


# ─── Normalización de nombres de columna ──────────────────────────────────────

def normalizar_col(nombre: str) -> str:
    """Normaliza un nombre de columna a snake_case sin tildes ni caracteres especiales.

    Convierte correctamente: á→a, é→e, í→i, ó→o, ú→u, ñ→n, espacios→_.
    Ejemplos:
        'CÓDIGO PAÍS' → 'codigo_pais'
        'Año'         → 'ano'
        'NOMBRE PAÍS' → 'nombre_pais'
        'TOTAL'       → 'total'
    """
    nombre = nombre.strip()
    # NFD descompone caracteres acentuados en base + diacrítico
    # Mn = Mark, Nonspacing (tildes, diéresis, etc.)
    nombre = unicodedata.normalize("NFD", nombre)
    nombre = "".join(c for c in nombre if unicodedata.category(c) != "Mn")
    nombre = nombre.lower()
    nombre = re.sub(r"[^a-z0-9]+", "_", nombre)
    return nombre.strip("_")


def normalizar_nombres(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica normalizar_col a todas las columnas del DataFrame."""
    df = df.copy()
    df.columns = [normalizar_col(c) for c in df.columns]
    return df


# ─── Lectura de Excel ─────────────────────────────────────────────────────────

def leer_hoja_excel(ruta: str, hoja: str) -> pd.DataFrame:
    """Lee una hoja Excel como texto puro y reemplaza cadenas vacías por NaN.

    - Usa dtype=str para evitar coerciones silenciosas (réplica de SCANTEXT=YES).
    - Valida existencia del archivo y de la hoja antes de leer.
    - Lanza FileNotFoundError / ValueError con mensajes accionables.
    """
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"Archivo no encontrado: {ruta}")

    with pd.ExcelFile(ruta, engine="openpyxl") as xf:
        if hoja not in xf.sheet_names:
            raise ValueError(
                f"Hoja '{hoja}' no encontrada en '{os.path.basename(ruta)}'. "
                f"Hojas disponibles: {xf.sheet_names}"
            )
        df = pd.read_excel(xf, sheet_name=hoja, dtype=str)

    df = df.apply(
        lambda col: col.str.strip().replace("", pd.NA) if col.dtype == object else col
    )
    return df


# ─── Validación de esquema ────────────────────────────────────────────────────

def validar_columnas(df: pd.DataFrame, requeridas: list[str], contexto: str) -> None:
    """Verifica que todas las columnas requeridas estén presentes en el DataFrame.

    Lanza ValueError con lista de columnas faltantes y disponibles si falla.
    """
    faltantes = [c for c in requeridas if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"[{contexto}] Columnas faltantes: {faltantes}. "
            f"Columnas disponibles: {list(df.columns)}"
        )


# ─── Alineación de schema RA ──────────────────────────────────────────────────

def alinear_a_schema_ra(df: pd.DataFrame, fuente: str) -> pd.DataFrame:
    """Proyecta un DataFrame al schema canónico ORDEN_FINAL_RA.

    Columnas presentes en ORDEN_FINAL_RA pero ausentes en df se agregan como "".
    Columnas extra (no en ORDEN_FINAL_RA) se descartan con un aviso.
    """
    df = df.copy()

    extra = [c for c in df.columns if c not in ORDEN_FINAL_RA]
    if extra:
        logger.debug("[%s] Columnas extras descartadas al alinear a RA: %s", fuente, extra)

    for col in ORDEN_FINAL_RA:
        if col not in df.columns:
            df[col] = np.nan

    result = df[ORDEN_FINAL_RA].copy()

    # Al concatenar fuentes de distinto origen (histórico Excel→str, parquets→tipos mixtos)
    # se producen columnas object con mezcla de str/int/float que pyarrow rechaza.
    # Solución: columnas monetarias se normalizan a float64; el resto a str.
    for col in result.columns:
        if col in _COLS_NUMERICAS_RA:
            result[col] = pd.to_numeric(result[col], errors="coerce")
        elif not pd.api.types.is_object_dtype(result[col]):
            result[col] = result[col].astype(str)

    return result
