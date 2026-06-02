"""Nodos del pipeline de Unión de Base RA — acumulación histórica mensual.

Migración del script SAS 'UnirBase F2026_01C2026_01.sas' a Python/Kedro.

Función del proceso
────────────────────────────────────────────────────────────────────────────────
Este pipeline implementa la ACUMULACIÓN HISTÓRICA de la Base de Registros
Administrativos. Cada mes se ejecuta para AGREGAR el mes corriente a la
base acumulada de todos los meses anteriores.

No confundir con `consolidacion_ra`, que une las fuentes RA del mes en curso
(Fletes + Cancillería) en memoria. Este pipeline toma esos resultados ya
procesados y los adhiere al histórico Excel.

Correspondencia SAS → Python
────────────────────────────────────────────────────────────────────────────────
%LET ANOF/MESF/ANOC/MESC              → params union_ra.anof/mesf/anoc/mesc
PROC IMPORT RA_0 (histórico)          → leer_base_historica → HistoricalRAStrategy
PROC IMPORT FLETES_1                  → fletes_maestro (parquet) → FletesStrategy
CANCILLERIA_1 comentado               → fuentes_activas.cancilleria: false
DATA RA_1; SET RA_0 FLETES_1;         → acumular_fuentes (usa estrategias)
PROC SORT DATA=RA_1; BY PERIODO_MES;  → acumular_fuentes (sort_values)
PROC EXPORT OUTFILE=...F&ANOF&MESF... → exportar_base_acumulada

Decisión de diseño clave
────────────────────────────────────────────────────────────────────────────────
El SAS leía las fuentes mensuales directamente desde sus Excel de salida.
En Kedro, usamos los Parquet intermedios (fletes_maestro, canc_maestro) para
evitar la dependencia de archivos Excel intermedios. El resultado final se
exporta a Excel para compatibilidad con el flujo existente.
"""
from __future__ import annotations

import logging
import os

import pandas as pd

from emces.utils import leer_hoja_excel
from emces.strategies.source_strategy import (
    CancilleriaStrategy,
    FletesStrategy,
    HistoricalRAStrategy,
    SourceStrategy,
)

logger = logging.getLogger(__name__)

# Columna de ordenamiento — presente en todas las fuentes RA
_COL_ORDEN = "periodo_mes"


# ─── Nodos ────────────────────────────────────────────────────────────────────

def leer_base_historica(
    ruta_entrada: str,
    archivo_historico: str,
    hoja_historico: str,
) -> pd.DataFrame:
    """Lee la base RA acumulada del mes anterior desde un archivo Excel.

    Equivale a:
        PROC IMPORT OUT=RA_0
        DATAFILE= "&SALIDA\\BaseEMCES-RA_...xlsx"
        SHEET='RA'N;

    El archivo histórico contiene todos los meses procesados hasta el período
    anterior al corriente. Su nombre incluye el sufijo del último procesamiento,
    ej. 'BaseEMCES-RA_2022-1_F2512C2601.xlsx'.

    La lectura física del Excel se hace aquí (fuera del catálogo) porque el
    nombre del archivo es dinámico y se construye desde parameters.yml. La
    preparación del DataFrame (normalización, validación, alineación al schema)
    se delega a HistoricalRAStrategy.

    Args:
        ruta_entrada:     Directorio donde se encuentra el histórico
                          (data/03_primary/ por convención del proyecto).
        archivo_historico: Nombre del Excel histórico. Se actualiza en
                           parameters.yml cada mes antes de ejecutar.
        hoja_historico:   Nombre de la hoja dentro del Excel (normalmente 'RA').

    Returns:
        DataFrame con el histórico RA, alineado al schema ORDEN_FINAL_RA.
    """
    ruta = os.path.join(ruta_entrada, archivo_historico)
    df_raw = leer_hoja_excel(ruta, hoja_historico)

    strategy = HistoricalRAStrategy()
    df = strategy.prepare(df_raw)  # read (norm cols) → validate_schema → transform

    logger.info(
        "ra_historico: %d filas leídas de '%s' (hoja='%s')",
        len(df), archivo_historico, hoja_historico,
    )
    return df


def acumular_fuentes(
    ra_historico: pd.DataFrame,
    fletes_maestro: pd.DataFrame,
    canc_maestro: pd.DataFrame,
    fuentes_activas: dict[str, bool],
) -> pd.DataFrame:
    """Concatena el histórico con las fuentes mensuales activas y ordena.

    Equivale en SAS a:
        DATA RA_1;
        SET RA_0 FLETES_1 [CANCILLERIA_1];   ← CANCILLERIA_1 comentado si inactiva
        RUN;
        PROC SORT DATA=RA_1; BY PERIODO_MES; RUN;

    El parámetro `fuentes_activas` replica el mecanismo de comentar/descomentar
    PROC IMPORT en el SAS original. Permite activar/desactivar fuentes sin
    modificar el código, solo cambiando parameters.yml.

    Antes de usar cada fuente se ejecuta strategy.prepare(), que encapsula:
      - read():            pre-procesamiento específico de la fuente
      - validate_schema(): validación de columnas y coherencia
      - transform():       alineación al schema canónico ORDEN_FINAL_RA

    Validaciones adicionales respecto al SAS original:
      - Incompatibilidad de schema entre fuentes (columnas distintas) → warning
      - Solapamiento de periodos entre histórico y fuente nueva → warning

    Args:
        ra_historico:    Base acumulada hasta el mes anterior
                         (ya procesada por HistoricalRAStrategy en leer_base_historica).
        fletes_maestro:  Resultado del pipeline fletes del mes corriente.
        canc_maestro:    Resultado del pipeline cancilleria (se ignora si inactivo).
        fuentes_activas: Dict con claves 'fletes' y 'cancilleria' (bool).
                         Ejemplo: {fletes: true, cancilleria: false}

    Returns:
        DataFrame con histórico + fuentes activas, ordenado por periodo_mes,
        con todas las columnas de ORDEN_FINAL_RA.
    """
    # Defensa de profundidad: aunque HistoricalRAStrategy.validate_schema() ya
    # verifica esto en leer_base_historica, acumular_fuentes puede recibir el
    # histórico vacío en tests unitarios o si se invoca directamente.
    if ra_historico.empty:
        raise ValueError(
            "La base histórica (ra_historico) está vacía. "
            "Verifique 'archivo_historico' en parameters.yml y que el archivo exista."
        )

    # Recolectar fuentes activas para verificación de compatibilidad de schema
    fuentes_brutas: list[pd.DataFrame] = []
    nombres_fuentes: list[str] = []

    if fuentes_activas.get("fletes", True):
        fuentes_brutas.append(fletes_maestro)
        nombres_fuentes.append("fletes")

    if fuentes_activas.get("cancilleria", False):
        fuentes_brutas.append(canc_maestro)
        nombres_fuentes.append("cancilleria")

    # Comparar schemas de las fuentes nuevas antes de transformar.
    # Detecta columnas presentes en una fuente pero no en otra.
    if len(fuentes_brutas) > 1:
        SourceStrategy.verificar_compatibilidad(fuentes_brutas, nombres_fuentes)

    # ── Acumular: histórico (ya preparado) + fuentes nuevas vía Strategy ───────
    # ra_historico ya pasó por HistoricalRAStrategy.prepare() en leer_base_historica
    partes: list[pd.DataFrame] = [ra_historico]
    resumen: list[str] = [f"historico={len(ra_historico)}"]

    if fuentes_activas.get("fletes", True):
        # Equivale a: FLETES_1 activo en el SET de SAS
        strategy_fletes = FletesStrategy()
        SourceStrategy.verificar_duplicados_periodo(ra_historico, fletes_maestro, "fletes")
        df_fletes = strategy_fletes.prepare(fletes_maestro)
        partes.append(df_fletes)
        resumen.append(f"fletes={len(df_fletes)}")
        logger.info("  Fletes ACTIVO: %d filas incluidas", len(df_fletes))
    else:
        # Equivale a: PROC IMPORT FLETES_1 comentado en el SAS original
        logger.info("  Fletes INACTIVO — omitido según fuentes_activas")

    if fuentes_activas.get("cancilleria", False):
        # Equivale a: CANCILLERIA_1 descomentado en el SET de SAS
        strategy_canc = CancilleriaStrategy()
        SourceStrategy.verificar_duplicados_periodo(ra_historico, canc_maestro, "cancilleria")
        df_canc = strategy_canc.prepare(canc_maestro)
        partes.append(df_canc)
        resumen.append(f"cancilleria={len(df_canc)}")
        logger.info("  Cancillería ACTIVA: %d filas incluidas", len(df_canc))
    else:
        # Equivale a: PROC IMPORT CANCILLERIA_1 comentado en el SAS original
        logger.info("  Cancillería INACTIVA — omitida según fuentes_activas")

    # DATA RA_1; SET RA_0 FLETES_1 [CANCILLERIA_1];
    base_acumulada = pd.concat(partes, ignore_index=True)

    # PROC SORT DATA=RA_1; BY PERIODO_MES;
    # PERIODO_MES en formato "YYYY_MM" → sort lexicográfico es correcto
    base_acumulada = (
        base_acumulada
        .sort_values(_COL_ORDEN, na_position="last")
        .reset_index(drop=True)
    )

    periodos = sorted(base_acumulada[_COL_ORDEN].dropna().unique())
    logger.info(
        "base_ra_acumulada: %d filas totales (%s) | periodos: %s..%s",
        len(base_acumulada),
        " + ".join(resumen),
        periodos[0] if periodos else "?",
        periodos[-1] if periodos else "?",
    )
    return base_acumulada


def exportar_base_acumulada(
    base_ra_acumulada: pd.DataFrame,
    ruta_salida: str,
    prefijo_salida: str,
    anof: str,
    mesf: str,
    anoc: str,
    mesc: str,
    hoja_salida: str,
) -> dict[str, object]:
    """Exporta la base RA acumulada a Excel con nombre dinámico.

    Equivale a:
        PROC EXPORT DATA=RA_1
        OUTFILE= "&SALIDA.\\BaseEMCES-RA_2022-1_F&ANOF.&MESF.C&ANOC.&MESC..xlsx"
        SHEET="RA";

    Convención de nombre: {prefijo}_F{anof}{mesf}C{anoc}{mesc}.xlsx
    Ejemplo:              BaseEMCES-RA_2022-1_F2601C2601.xlsx

    Args:
        base_ra_acumulada: DataFrame con el histórico completo actualizado.
        ruta_salida:       Directorio de salida (data/03_primary/ por convención).
        prefijo_salida:    Parte fija del nombre, ej. 'BaseEMCES-RA_2022-1'.
        anof, mesf:        Año y mes (2 dígitos) del último procesamiento Fletes.
        anoc, mesc:        Año y mes (2 dígitos) del último procesamiento Cancillería.
        hoja_salida:       Nombre de la hoja en el Excel de salida (normalmente 'RA').

    Returns:
        Dict con metadata de la exportación para trazabilidad y auditoría.
    """
    if base_ra_acumulada.empty:
        raise ValueError("base_ra_acumulada está vacía — no se exporta el Excel.")

    nombre_archivo = f"{prefijo_salida}_F{anof}{mesf}C{anoc}{mesc}.xlsx"
    ruta_completa = os.path.join(ruta_salida, nombre_archivo)

    os.makedirs(ruta_salida, exist_ok=True)
    base_ra_acumulada.to_excel(
        ruta_completa,
        sheet_name=hoja_salida,
        index=False,
        engine="openpyxl",
    )

    periodos = sorted(base_ra_acumulada["periodo_mes"].dropna().unique())

    logger.info(
        "Exportado: %s | filas=%d | hoja='%s' | periodos=%s..%s",
        ruta_completa, len(base_ra_acumulada), hoja_salida,
        periodos[0] if periodos else "?",
        periodos[-1] if periodos else "?",
    )

    return {
        "ruta": ruta_completa,
        "nombre_archivo": nombre_archivo,
        "filas": len(base_ra_acumulada),
        "hoja": hoja_salida,
        "periodos": periodos,
        "anof": anof, "mesf": mesf,
        "anoc": anoc, "mesc": mesc,
    }
