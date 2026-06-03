"""Nodos del pipeline de análisis comparativo interperiódico — FASE 5.

Replica exactamente los data steps finales de SIPSA_A_MODELO_IPC.sas
que enriquecen TD_Total con las variaciones porcentuales:

  VariacMensual1 = (MesActual - MesAnterior) * 100 / MesAnterior;
  VariacAnual1   = (MesActual - AnoAnterior)  * 100 / AnoAnterior;
  VariacMensual  = cat(VariacMensual1, "%");   /* con coma colombiana */
  VariacAnual    = cat(VariacAnual1,   "%");

El formato de salida replica SAS BEST12.: hasta 12 dígitos significativos,
sin ceros finales, con coma como separador decimal (estilo colombiano).
"""
from __future__ import annotations

import logging
import math

import pandas as pd

log = logging.getLogger(__name__)


def calcular_variaciones(td_total: pd.DataFrame) -> pd.DataFrame:
    """Enriquece TD_Total con VariacMensual% y VariacAnual% estilo SAS.

    Toma la tabla TD_Total producida en F4 — que ya contiene las toneladas
    acumuladas por artículo en los tres períodos — y agrega dos columnas
    de variación porcentual formateadas con coma como separador decimal y
    símbolo ``%`` al final, exactamente como el programa SAS original.

    Fórmulas (equivalente SAS):
        VariacMensual = (MesActual - MesAnterior) / MesAnterior * 100
        VariacAnual   = (MesActual - AnoAnterior)  / AnoAnterior * 100

    Args:
        td_total: DataFrame de F4 con columnas ``AbastTotal_MesActual``,
            ``AbastTotal_MesAnterior`` y ``AbastTotal_AnoAnterior``.

    Returns:
        DataFrame con las mismas columnas de F4 más:
            - ``VariacMensual_num``: variación mensual en % (float).
            - ``VariacAnual_num``:   variación anual en % (float).
            - ``VariacMensual``:     cadena formateada estilo colombiano.
            - ``VariacAnual``:       cadena formateada estilo colombiano.
    """
    df = td_total.copy()

    df["VariacMensual_num"] = _variacion_pct(
        df["AbastTotal_MesActual"], df["AbastTotal_MesAnterior"]
    )
    df["VariacAnual_num"] = _variacion_pct(
        df["AbastTotal_MesActual"], df["AbastTotal_AnoAnterior"]
    )

    df["VariacMensual"] = df["VariacMensual_num"].map(_formatear_variacion)
    df["VariacAnual"] = df["VariacAnual_num"].map(_formatear_variacion)

    n_sin_mensual = int(df["VariacMensual_num"].isna().sum())
    n_sin_anual = int(df["VariacAnual_num"].isna().sum())

    log.info(
        "calcular_variaciones OK | articulos=%d | sin_vaiac_mensual=%d | sin_vaiac_anual=%d",
        len(df),
        n_sin_mensual,
        n_sin_anual,
    )
    return df


# ─── helpers privados ─────────────────────────────────────────────────────────

def _variacion_pct(actual: pd.Series, base: pd.Series) -> pd.Series:
    """Calcula (actual - base) / base * 100. NaN si base == 0 o NaN."""
    return ((actual - base) / base * 100).where(base.ne(0) & base.notna())


def _formatear_variacion(valor: float) -> str:
    """Convierte un float a cadena estilo SAS BEST12. con coma colombiana.

    Equivalente SAS:
        VariacMensual = cat(VariacMensual1, "%");
        VariacMensual = tranwrd(VariacMensual, '.', ',');

    Usa hasta 12 dígitos significativos sin ceros finales (BEST12.),
    coma como separador decimal y símbolo % al final.

    Args:
        valor: Variación porcentual como float. NaN retorna cadena vacía.

    Returns:
        Cadena como ``"-3,159874912%"`` o ``""`` si el valor es NaN/infinito.
    """
    if valor is None or (isinstance(valor, float) and (math.isnan(valor) or math.isinf(valor))):
        return ""
    # g format: hasta N dígitos significativos, sin ceros finales, sin notación científica
    # 12 sig digits = equivalente a SAS BEST12.
    texto = f"{valor:.12g}"
    return texto.replace(".", ",") + "%"
