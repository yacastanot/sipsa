"""Nodos de consolidación de Registros Administrativos EMCES.

Implementa la 'Función RA: Consolidación bases RA EMCES' del diagrama de flujo.

Toma los DataFrames finales de cada sub-proceso RA (Fletes, Cancillería y
futuros como Viajes), los alinea al schema canónico ORDEN_FINAL_RA y los
concatena en una única Base de Registros Administrativos.

Por qué existe este nodo separado en lugar de hacerlo en cada pipeline:
  - Desacopla la lógica de fuente de la lógica de unión.
  - Permite agregar nuevas fuentes RA (Viajes, etc.) sin tocar Fletes ni Cancillería.
  - La Base RA resultante es la entrada de la consolidación con la Encuesta EMCES.
"""
from __future__ import annotations

import logging

import pandas as pd

from emces.utils import ORDEN_FINAL_RA, alinear_a_schema_ra, validar_columnas

logger = logging.getLogger(__name__)

# Columnas mínimas que cualquier fuente RA debe aportar antes de consolidar.
# Garantizan trazabilidad y métricas básicas en la base unificada.
_COLS_MINIMAS_RA: list[str] = [
    "flujo_comercial", "periodo", "mes", "periodo_mes",
    "pais", "descripcion_cabps",
    "total_en_dolares", "total_en_miles_de_pesos",
]


def consolidar_ra(
    df_fletes: pd.DataFrame,
    df_cancilleria: pd.DataFrame,
) -> pd.DataFrame:
    """Une Fletes EMCES y Cancillería EMCES en la Base de Registros Administrativos.

    Pasos:
      1. Valida columnas mínimas en cada fuente.
      2. Alinea ambas al schema ORDEN_FINAL_RA (columnas faltantes → "").
      3. Concatena y registra el volumen por fuente.

    Cuando se incorpore Viajes, se agrega df_viajes como tercer argumento.

    Args:
        df_fletes:      Salida de fletes_maestro (pipeline fletes).
        df_cancilleria: Salida de canc_maestro (pipeline cancilleria).

    Returns:
        DataFrame con el schema ORDEN_FINAL_RA, listo para la consolidación
        con la Encuesta EMCES.
    """
    fuentes: list[tuple[str, pd.DataFrame]] = [
        ("fletes", df_fletes),
        ("cancilleria", df_cancilleria),
    ]

    partes: list[pd.DataFrame] = []
    for nombre, df in fuentes:
        validar_columnas(df, _COLS_MINIMAS_RA, f"consolidar_ra[{nombre}]")
        df_alineado = alinear_a_schema_ra(df, fuente=nombre)
        partes.append(df_alineado)
        logger.info(
            "  %-15s → %d filas, flujos: %s",
            nombre, len(df_alineado),
            df_alineado["flujo_comercial"].unique().tolist(),
        )

    base_ra = pd.concat(partes, ignore_index=True)

    if base_ra.empty:
        raise ValueError(
            "Base RA consolidada vacía. Revise que fletes_maestro y "
            "canc_maestro tengan datos."
        )

    logger.info(
        "base_ra: %d filas totales (fletes=%d, cancilleria=%d)",
        len(base_ra), len(df_fletes), len(df_cancilleria),
    )
    return base_ra


def generar_resumen_ra(base_ra: pd.DataFrame) -> dict[str, object]:
    """Genera un resumen estadístico de la Base RA consolidada.

    Útil para auditoría y detección de anomalías antes de la consolidación
    con la Encuesta EMCES.

    Returns:
        Dict con métricas clave: total filas, filas por flujo, suma monetaria.
    """
    resumen: dict[str, object] = {
        "total_filas": len(base_ra),
        "periodo_mes": base_ra["periodo_mes"].unique().tolist(),
        "flujos": base_ra["flujo_comercial"].value_counts().to_dict(),
        "paises_distintos": base_ra["pais"].nunique(),
        "sum_total_en_dolares": float(
            pd.to_numeric(base_ra["total_en_dolares"], errors="coerce").sum()
        ),
        "sum_total_en_miles_de_pesos": float(
            pd.to_numeric(base_ra["total_en_miles_de_pesos"], errors="coerce").sum()
        ),
    }

    logger.info(
        "Resumen RA — filas: %d | países: %d | total USD: %.2f | total M$: %.2f",
        resumen["total_filas"],
        resumen["paises_distintos"],
        resumen["sum_total_en_dolares"],
        resumen["sum_total_en_miles_de_pesos"],
    )
    return resumen
