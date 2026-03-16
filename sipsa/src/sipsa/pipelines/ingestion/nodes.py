"""Nodos de ingesta: lectura y validación del Excel de entrada semanal."""
import logging
import os

import pandas as pd

logger = logging.getLogger(__name__)

COLUMNAS_ESPERADAS = {"Grupo", "Producto", "Fuente", "Min(1)", "Max(1)", "P(1)", "P(-1)", "Tend"}


def leer_entrada(ruta_entrada: str, archivo_entrada: str) -> pd.DataFrame:
    """Lee el Excel semanal desde la ruta configurada, valida columnas y estandariza tipos.

    Args:
        ruta_entrada: Directorio donde está el archivo de entrada (ej. "data/01_raw").
        archivo_entrada: Nombre del archivo Excel (ej. "Listado a 27 feb 26.xlsx").

    Returns:
        DataFrame validado con columnas estandarizadas y sin filas vacías.
    """
    ruta_completa = os.path.join(ruta_entrada, archivo_entrada)
    logger.info("Leyendo archivo de entrada: %s", ruta_completa)

    df = pd.read_excel(ruta_completa, engine="openpyxl")

    faltantes = COLUMNAS_ESPERADAS - set(df.columns)
    if faltantes:
        raise ValueError(f"Columnas faltantes en el archivo de entrada: {faltantes}")

    # Eliminar filas donde Producto o Fuente están vacíos
    df = df.dropna(subset=["Producto", "Fuente"])
    df = df[df["Producto"].astype(str).str.strip() != ""]
    df = df[df["Fuente"].astype(str).str.strip() != ""]

    # Normalizar tipos
    for col in ["Min(1)", "Max(1)", "P(1)", "P(-1)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Tend"] = df["Tend"].fillna("n.d.").astype(str).str.strip()
    df["Grupo"] = df["Grupo"].astype(str).str.strip()
    df["Producto"] = df["Producto"].astype(str).str.strip()
    df["Fuente"] = df["Fuente"].astype(str).str.strip()

    logger.info("Entrada leída: %d filas, %d columnas.", len(df), len(df.columns))
    return df
