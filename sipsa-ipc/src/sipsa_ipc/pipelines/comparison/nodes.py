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

    SAS BEST12. usa 12 COLUMNAS totales (signo + parte entera + coma + decimales),
    no 12 dígitos significativos. Para valores negativos el signo ocupa 1 columna,
    reduciendo los dígitos disponibles. Los ceros finales se eliminan.

    Ejemplos verificados vs SAS:
        -3.15987491238 → "-3,159874912%"   (12 cols: - + 3 + , + 9 decimales)
         7.96708264345 →  "7,9670826435%"  (12 cols:     7 + , + 10 decimales)
       -13.3125069287  → "-13,31250693%"   (12 cols: - + 13 + , + 8 decimales)

    Args:
        valor: Variación porcentual como float. NaN retorna cadena vacía.

    Returns:
        Cadena como ``"-3,159874912%"`` o ``""`` si el valor es NaN/infinito.
    """
    if valor is None or (isinstance(valor, float) and (math.isnan(valor) or math.isinf(valor))):
        return ""
    if valor == 0.0:
        return "0%"

    abs_val = abs(valor)
    sign_chars = 1 if valor < 0 else 0

    # Dígitos enteros: max 1 para valores < 1 (el "0" delante de la coma)
    int_digits = max(1, math.floor(math.log10(abs_val)) + 1) if abs_val >= 1 else 1

    # BEST12.: 12 chars = sign_chars + int_digits + 1(coma) + frac_chars
    frac_chars = max(0, 12 - sign_chars - int_digits - 1)

    if abs_val >= 1:
        # sig_digits = integer digits + fractional digits
        sig_digits = max(1, int_digits + frac_chars)
    else:
        # For values < 1, fractional chars include leading zeros (e.g. "0.057" → 1 leading zero).
        # Those leading zeros consume fractional columns but are not significant digits,
        # so subtract them from frac_chars to get the correct g-format precision.
        leading_zeros = math.floor(-math.log10(abs_val))
        sig_digits = max(1, frac_chars - leading_zeros)

    texto = f"{valor:.{sig_digits}g}"
    return texto.replace(".", ",") + "%"
