"""Patrón Strategy para fuentes de Registros Administrativos EMCES.

Cada fuente RA (histórico, Fletes, Cancillería, Viajes futuro, etc.) tiene
particularidades propias en cuanto a normalización de columnas, validaciones
requeridas y coerciones de tipo. Este módulo encapsula esas diferencias mediante
el patrón Strategy, de modo que agregar una nueva fuente no requiera modificar
el nodo de acumulación, sino únicamente crear una nueva subclase de SourceStrategy
y registrarla en SOURCE_REGISTRY.

Correspondencia con el SAS original (UnirBase F2026_01C2026_01.sas)
─────────────────────────────────────────────────────────────────────────────
  PROC IMPORT OUT=RA_0       → HistoricalRAStrategy (leer_base_historica)
  PROC IMPORT OUT=FLETES_1   → FletesStrategy       (fletes_maestro parquet)
  PROC IMPORT OUT=CANC_1     → CancilleriaStrategy  (canc_maestro parquet)
  DATA RA_1; SET RA_0 F C;   → acumular_fuentes usa strategy.prepare() por fuente

Uso en nodos
─────────────────────────────────────────────────────────────────────────────
  strategy = FletesStrategy()
  df_preparado = strategy.prepare(df_fletes_maestro)
  # equivale a: read() → validate_schema() → transform()

Extender con nueva fuente
─────────────────────────────────────────────────────────────────────────────
  1. Crear class ViajesStrategy(SourceStrategy) con sus 3 métodos abstractos.
  2. Agregar una entrada en SOURCE_REGISTRY: {"viajes": ViajesStrategy()}.
  3. Agregar "viajes_maestro" como input al nodo acumular_fuentes en pipeline.py.
  4. Activar en parameters.yml: union_ra.fuentes_activas.viajes: true
"""
from __future__ import annotations

import logging
import warnings
from abc import ABC, abstractmethod

import pandas as pd

from emces.utils import (
    ORDEN_FINAL_RA,
    alinear_a_schema_ra,
    validar_columnas,
)

logger = logging.getLogger(__name__)

# ─── Columnas mínimas por tipo de fuente ─────────────────────────────────────

# Columnas que cualquier fuente mensual nueva debe traer (mínimo funcional)
COLS_BASE_FUENTE_NUEVA: list[str] = ["flujo_comercial", "periodo", "mes", "periodo_mes"]

# Columnas que el histórico Excel debe tener (incluye campos financieros clave
# para detectar archivos corruptos o de otra estructura a tiempo)
COLS_MINIMAS_HISTORICO: list[str] = [
    "flujo_comercial", "periodo", "mes", "periodo_mes",
    "pais", "total_en_dolares", "total_en_miles_de_pesos",
]


# ─── Interfaz abstracta ───────────────────────────────────────────────────────

class SourceStrategy(ABC):
    """Interfaz abstracta para fuentes de Registros Administrativos EMCES.

    Define el contrato que cada fuente RA debe cumplir para poder ser incluida
    en la base acumulada. Los métodos abstractos capturan las diferencias entre
    fuentes; `prepare()` orquesta el flujo completo.

    Métodos abstractos (deben implementarse en cada subclase):
        get_source_name()  → str     : identificador para logs y trazabilidad.
        validate_schema()  → None    : lanza ValueError si faltan columnas críticas.
        transform()        → DataFrame: proyecta al schema canónico ORDEN_FINAL_RA.

    Métodos con implementación base (se pueden sobrescribir):
        read()    → DataFrame: pre-procesa el DataFrame ya cargado por Kedro.
                               Por defecto es identidad; el histórico lo sobrescribe
                               para normalizar mayúsculas.
        prepare() → DataFrame: orquesta read → validate_schema → transform.
    """

    @abstractmethod
    def get_source_name(self) -> str:
        """Nombre identificador de la fuente (para logs y trazabilidad)."""

    @abstractmethod
    def validate_schema(self, df: pd.DataFrame) -> None:
        """Valida que el DataFrame tiene las columnas requeridas por esta fuente.

        Debe:
        - Lanzar ValueError si faltan columnas críticas (periodo_mes, flujo_comercial…).
        - Emitir warnings.warn para condiciones de riesgo que no son error fatal.
        - Verificar que el DataFrame no esté vacío.
        """

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Proyecta el DataFrame al schema canónico ORDEN_FINAL_RA.

        Debe retornar un DataFrame con exactamente las columnas de ORDEN_FINAL_RA,
        con columnas monetarias en float64 y el resto en str/object.
        """

    def read(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pre-procesa el DataFrame ya cargado por Kedro (por defecto: identidad).

        Nota arquitectural: la lectura física del archivo es responsabilidad del
        Kedro Data Catalog o del nodo dedicado (leer_base_historica). Este método
        actúa sobre el DataFrame YA cargado, aplicando normalizaciones específicas
        de la fuente que deben ocurrir ANTES de validate_schema().

        Ejemplos de uso:
        - HistoricalRAStrategy.read(): normaliza columnas a minúsculas porque el
          Excel histórico puede tenerlas en MAYÚSCULAS o en CamelCase.
        - FletesStrategy, CancilleriaStrategy: el parquet ya tiene nombres
          normalizados (producidos por sus respectivos pipelines), no requieren
          transformación previa.
        """
        return df

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Punto de entrada principal: read → validate_schema → transform.

        Orquesta los tres pasos del pipeline de preparación de una fuente.
        Registra en log las métricas básicas del resultado.

        Returns:
            DataFrame alineado al schema ORDEN_FINAL_RA, listo para concatenar.
        """
        df = self.read(df)
        self.validate_schema(df)
        df_preparado = self.transform(df)
        self._log_resultado(df_preparado)
        return df_preparado

    def _log_resultado(self, df: pd.DataFrame) -> None:
        """Registra filas, columnas y periodos detectados tras prepare()."""
        periodos: list[str] = []
        if "periodo_mes" in df.columns:
            periodos = sorted(df["periodo_mes"].dropna().unique().tolist())
        logger.info(
            "[%s] %d filas preparadas | cols=%d | periodos: %s",
            self.get_source_name(),
            len(df),
            len(df.columns),
            periodos,
        )

    # ── Utilidades de clase ────────────────────────────────────────────────────

    @staticmethod
    def verificar_compatibilidad(
        fuentes: list[pd.DataFrame],
        nombres: list[str],
    ) -> None:
        """Emite warnings cuando columnas presentes en una fuente faltan en otras.

        Útil para detectar diferencias de schema entre fuentes ANTES de alinear
        al schema canónico, equivalente a la inspección post-SET en SAS.
        Se llama sobre los DataFrames RAW (antes de transform()) para que los
        avisos sean informativos sobre las diferencias reales entre fuentes.

        Args:
            fuentes: Lista de DataFrames a comparar.
            nombres: Lista de nombres (mismo orden que fuentes) para los mensajes.
        """
        if len(fuentes) < 2:
            return
        cols_por_fuente = {n: set(f.columns) for n, f in zip(nombres, fuentes)}
        todas = set().union(*cols_por_fuente.values())
        for nombre, cols in cols_por_fuente.items():
            faltantes = todas - cols
            if faltantes:
                warnings.warn(
                    f"[{nombre}] Columnas presentes en otras fuentes pero ausentes aquí: "
                    f"{sorted(faltantes)}. Se completarán con cadena vacía al alinear.",
                    stacklevel=3,
                )

    @staticmethod
    def verificar_duplicados_periodo(
        historico: pd.DataFrame,
        nueva_fuente: pd.DataFrame,
        nombre_fuente: str,
    ) -> None:
        """Advierte si el histórico ya contiene periodos de la nueva fuente.

        En el SAS original no había esta validación; si se ejecutaba dos veces
        el mismo mes, los datos se duplicaban silenciosamente. Este método
        previene ese problema.

        Args:
            historico:     Base acumulada de meses anteriores (ya cargada).
            nueva_fuente:  DataFrame del mes corriente a agregar.
            nombre_fuente: Nombre de la fuente (para el mensaje de warning).
        """
        if "periodo_mes" not in historico.columns or "periodo_mes" not in nueva_fuente.columns:
            return
        periodos_historico = set(historico["periodo_mes"].dropna().unique())
        periodos_nuevos = set(nueva_fuente["periodo_mes"].dropna().unique())
        solapamiento = periodos_historico & periodos_nuevos
        if solapamiento:
            warnings.warn(
                f"[{nombre_fuente}] El histórico ya contiene los periodos "
                f"{sorted(solapamiento)}. Agregar esta fuente generará DUPLICADOS. "
                "Verifique 'archivo_historico' en parameters.yml o deshabilite "
                f"la fuente en fuentes_activas.{nombre_fuente}.",
                stacklevel=3,
            )


# ─── Estrategias concretas ────────────────────────────────────────────────────

class HistoricalRAStrategy(SourceStrategy):
    """Estrategia para la base RA acumulada del mes anterior (Excel histórico).

    Corresponde al bloque PROC IMPORT OUT=RA_0 del SAS original:
        PROC IMPORT OUT=RA_0
            DATAFILE="&SALIDA.\\BaseEMCES-RA_2022-1_F2512C2601.xlsx"
            DBMS=xlsx REPLACE;
            SHEET='RA'N;
        RUN;

    El Excel histórico puede tener nombres de columna en MAYÚSCULAS o en
    capitalización inconsistente (depende de qué versión lo generó). Por eso
    `read()` normaliza a minúsculas antes de validar.
    """

    def get_source_name(self) -> str:
        return "historico"

    def read(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza nombres de columna a minúsculas y elimina espacios.

        Necesario porque el Excel histórico puede tener columnas en
        MAYÚSCULAS (exportado desde SAS) o en CamelCase (exportado desde
        una versión anterior de este pipeline).
        """
        df = df.copy()
        df.columns = [c.lower().strip() for c in df.columns]
        return df

    def validate_schema(self, df: pd.DataFrame) -> None:
        """Valida que el histórico tiene columnas mínimas y no está vacío."""
        if df.empty:
            raise ValueError(
                f"[{self.__class__.__name__}] El histórico está vacío. "
                "Verifique 'archivo_historico' en parameters.yml y que el archivo "
                "exista en la ruta indicada."
            )
        validar_columnas(df, COLS_MINIMAS_HISTORICO, self.__class__.__name__)

        n_periodos = df["periodo_mes"].nunique()
        logger.info(
            "[%s] Histórico con %d filas y %d periodos distintos.",
            self.get_source_name(), len(df), n_periodos,
        )

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Proyecta al schema canónico; columnas extras del Excel se descartan."""
        return alinear_a_schema_ra(df, fuente=self.get_source_name())


class FletesStrategy(SourceStrategy):
    """Estrategia para el resultado mensual del pipeline de Fletes.

    Corresponde al bloque PROC IMPORT OUT=FLETES_1 del SAS original:
        PROC IMPORT OUT=FLETES_1
            DATAFILE="&ENTRADA.\\Fletes_EMCES_&ANOF..&MESF..xlsx"
            DBMS=xlsx REPLACE;
            SHEET="Fletes_EMCES_&ANOF..&MESF.";
        RUN;

    En Kedro, fletes_maestro es un Parquet producido por el pipeline 'fletes',
    con columnas ya normalizadas y tipos correctos. Solo se necesita alinear
    al schema RA canónico y verificar que PERIODO_MES esté presente.
    """

    def get_source_name(self) -> str:
        return "fletes"

    def validate_schema(self, df: pd.DataFrame) -> None:
        """Valida columnas mínimas y detecta múltiples periodos inesperados."""
        if df.empty:
            raise ValueError(
                f"[{self.__class__.__name__}] fletes_maestro está vacío. "
                "Ejecute primero 'kedro run --pipeline fletes'."
            )
        validar_columnas(df, COLS_BASE_FUENTE_NUEVA, self.__class__.__name__)

        n_periodos = df["periodo_mes"].nunique()
        if n_periodos > 1:
            logger.warning(
                "[%s] fletes_maestro contiene %d periodos distintos: %s. "
                "Se esperaba un único mes. Verifique el parquet.",
                self.get_source_name(),
                n_periodos,
                sorted(df["periodo_mes"].dropna().unique().tolist()),
            )

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Proyecta al schema RA canónico; columnas extras del pipeline se descartan."""
        return alinear_a_schema_ra(df, fuente=self.get_source_name())


class CancilleriaStrategy(SourceStrategy):
    """Estrategia para el resultado mensual del pipeline de Cancillería.

    Corresponde al bloque PROC IMPORT OUT=CANCILLERIA_1 del SAS original
    (normalmente comentado cuando Cancillería no está disponible para el mes):
        /*
        PROC IMPORT OUT=CANCILLERIA_1
            DATAFILE="&ENTRADA.\\Cancillería_&ANOC..&MESC..xlsx"
            DBMS=xlsx REPLACE;
            SHEET="Cancillería_&ANOC..&MESC.";
        RUN;
        */

    En Kedro, canc_maestro es un Parquet producido por el pipeline 'cancilleria',
    con columnas normalizadas y layout EMCES ya aplicado (construir_layout_emces).
    """

    def get_source_name(self) -> str:
        return "cancilleria"

    def validate_schema(self, df: pd.DataFrame) -> None:
        """Valida columnas mínimas y alerta sobre posible solapamiento con histórico."""
        if df.empty:
            raise ValueError(
                f"[{self.__class__.__name__}] canc_maestro está vacío. "
                "Ejecute primero 'kedro run --pipeline cancilleria'."
            )
        validar_columnas(df, COLS_BASE_FUENTE_NUEVA, self.__class__.__name__)

        periodos = sorted(df["periodo_mes"].dropna().unique().tolist())
        logger.info(
            "[%s] canc_maestro con periodos: %s — verifique que el histórico "
            "no los contenga ya (use verificar_duplicados_periodo).",
            self.get_source_name(), periodos,
        )

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Proyecta al schema RA canónico; columnas del layout EMCES se descartan si exceden."""
        return alinear_a_schema_ra(df, fuente=self.get_source_name())


# ─── Registro de estrategias ─────────────────────────────────────────────────
# Permite agregar nuevas fuentes sin modificar acumular_fuentes:
#   1. Crear la subclase de SourceStrategy.
#   2. Registrarla aquí.
#   3. Agregar el dataset al catalog.yml y al nodo en pipeline.py.
#   4. Activar en parameters.yml.
SOURCE_REGISTRY: dict[str, SourceStrategy] = {
    "historico": HistoricalRAStrategy(),
    "fletes": FletesStrategy(),
    "cancilleria": CancilleriaStrategy(),
    # "viajes": ViajesStrategy(),  # activar al implementar el pipeline viajes
}
