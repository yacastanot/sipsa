"""Tests unitarios — pipeline de ingesta SIPSA IPC (F1).

Cubre las tareas del cronograma:
  T6  — Nodo leer_base: importa DataFrame desde Excel/fixture y retorna bronze
  T8  — Validación columnas requeridas: Ali, Cant Kg, Fuente, FechaEncuesta,
         Departamento Proc., Municipio Proc.
  T9  — Schema pandera: tipos de dato, Cant Kg >= 0, FechaEncuesta datetime
  T10 — Pipeline integrado: leer_base end-to-end

Estrategia de tests:
  - leer_base() acepta un str (ruta de archivo).
  - Para tests unitarios rápidos usamos un archivo Excel temporal (tmp_path).
  - Los tests de validación de schema prueban directamente SCHEMA_RAW.
  - No se requiere el Excel de producción de 547K filas.
"""
from __future__ import annotations

import pandas as pd
import pytest

from sipsa_ipc.pipelines.ingestion.nodes import _verificar_columnas, leer_base
from sipsa_ipc.validations.schemas import COLUMNAS_REQUERIDAS, SCHEMA_RAW


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _base_real(n: int = 30) -> pd.DataFrame:
    """Crea un DataFrame que replica la estructura exacta del Excel DANE."""
    periodos = (
        [pd.Timestamp("2025-04-01")] * (n // 3)
        + [pd.Timestamp("2025-03-01")] * (n // 3)
        + [pd.Timestamp("2024-04-01")] * (n - 2 * (n // 3))
    )
    return pd.DataFrame(
        {
            "Fuente":                 ["Bogotá, Corabastos"] * n,
            "FechaEncuesta":          periodos,
            "HoraEncuesta":           ["03:30:00"] * n,
            "TipoVehiculo":           ["TP"] * n,
            "PlacaVehiculo":          ["WOU046"] * n,
            "Cod. Depto Proc.":       ["'15"] * n,
            "Departamento Proc.":     ["BOYACÁ"] * n,
            "Cod. Municipio Proc.":   ["'15638"] * n,
            "Municipio Proc.":        ["SÁCHICA"] * n,
            "Observaciones":          [None] * n,
            "Grupo":                  ["VERDURAS Y HORTALIZAS"] * n,
            "Codigo CPC":             ["'0125301"] * n,
            "Ali":                    ["Cebolla cabezona blanca"] * n,
            "Cant Pres":              [180.0] * n,
            "Pres":                   ["BULTO"] * n,
            "Peso Pres":              [50.0] * n,
            "Cant Kg":                [9000.0] * n,
            "Digitador":              [None] * n,
        }
    )


@pytest.fixture
def excel_valido(tmp_path):
    """Escribe un Excel temporal con la estructura real BASE SIPSA_A."""
    df = _base_real(30)
    ruta = str(tmp_path / "Base_SIPSA_IPC_test.xlsx")
    df.to_excel(ruta, sheet_name="BASE SIPSA_A", index=False)
    return ruta


@pytest.fixture
def excel_sin_col(tmp_path):
    """Excel sin columna Ali — para probar detección de columnas faltantes."""
    df = _base_real(10).drop(columns=["Ali"])
    ruta = str(tmp_path / "Base_SIPSA_sin_ali.xlsx")
    df.to_excel(ruta, sheet_name="BASE SIPSA_A", index=False)
    return ruta


# ─── T6: leer_base — lectura y retorno correcto ───────────────────────────────

class TestLeerBase:
    def test_retorna_mismo_numero_filas(self, excel_valido):
        result = leer_base(excel_valido)
        assert len(result) == 30

    def test_conserva_todas_las_columnas(self, excel_valido):
        result = leer_base(excel_valido)
        for col in COLUMNAS_REQUERIDAS:
            assert col in result.columns, f"Falta columna: {col}"

    def test_fechaencuesta_es_datetime(self, excel_valido):
        result = leer_base(excel_valido)
        assert pd.api.types.is_datetime64_any_dtype(result["FechaEncuesta"])

    def test_cant_kg_es_float(self, excel_valido):
        result = leer_base(excel_valido)
        assert pd.api.types.is_float_dtype(result["Cant Kg"])

    def test_archivo_inexistente_lanza_error(self, tmp_path):
        """Ruta inválida debe lanzar FileNotFoundError o ValueError de pandas."""
        with pytest.raises((FileNotFoundError, ValueError)):
            leer_base(str(tmp_path / "no_existe.xlsx"))

    def test_tres_periodos_presentes(self, excel_valido):
        result = leer_base(excel_valido)
        n_periodos = result["FechaEncuesta"].dt.to_period("M").nunique()
        assert n_periodos == 3


# ─── T8: verificación de columnas requeridas ─────────────────────────────────

class TestVerificarColumnas:
    @pytest.mark.parametrize("col_faltante", sorted(COLUMNAS_REQUERIDAS))
    def test_falla_si_falta_columna_requerida(self, col_faltante, tmp_path):
        """Cada columna requerida debe disparar ValueError si está ausente."""
        df = _base_real(5).drop(columns=[col_faltante])
        ruta = str(tmp_path / f"sin_{col_faltante.replace(' ', '_')}.xlsx")
        df.to_excel(ruta, sheet_name="BASE SIPSA_A", index=False)
        with pytest.raises(ValueError, match=col_faltante.replace(".", r"\.")):
            leer_base(ruta)

    def test_columnas_extras_son_permitidas(self, tmp_path):
        """Columnas adicionales no declaradas en el schema no deben causar error."""
        df = _base_real(5)
        df["ColExtra"] = "extra"
        ruta = str(tmp_path / "con_extras.xlsx")
        df.to_excel(ruta, sheet_name="BASE SIPSA_A", index=False)
        result = leer_base(ruta)
        assert "ColExtra" in result.columns

    def test_mensaje_error_indica_columnas_faltantes(self):
        """El ValueError debe nombrar las columnas faltantes explícitamente."""
        df_sin = _base_real(3).drop(columns=["Ali", "Cant Kg"])
        with pytest.raises(ValueError) as exc_info:
            _verificar_columnas(df_sin)
        mensaje = str(exc_info.value)
        assert "Ali" in mensaje
        assert "Cant Kg" in mensaje


# ─── T9: schema pandera ───────────────────────────────────────────────────────

class TestValidarSchema:
    def test_datos_validos_pasan_sin_excepcion(self, excel_valido):
        result = leer_base(excel_valido)
        assert len(result) > 0

    def test_cant_kg_negativo_viola_schema(self, tmp_path):
        """Cant Kg < 0 debe disparar SchemaErrors."""
        import pandera.errors as pe
        df = _base_real(5)
        df.loc[2, "Cant Kg"] = -100.0
        ruta = str(tmp_path / "cant_kg_neg.xlsx")
        df.to_excel(ruta, sheet_name="BASE SIPSA_A", index=False)
        with pytest.raises(pe.SchemaErrors):
            leer_base(ruta)

    def test_ali_nulo_viola_schema(self, tmp_path):
        """Ali nulo (nullable=False) debe disparar SchemaErrors."""
        import pandera.errors as pe
        df = _base_real(5)
        df.loc[0, "Ali"] = None
        ruta = str(tmp_path / "ali_nulo.xlsx")
        df.to_excel(ruta, sheet_name="BASE SIPSA_A", index=False)
        with pytest.raises(pe.SchemaErrors):
            leer_base(ruta)

    def test_observaciones_nulas_son_validas(self, tmp_path):
        """Observaciones nulas (~40% en datos reales) deben ser aceptadas."""
        df = _base_real(5)
        df["Observaciones"] = None
        ruta = str(tmp_path / "obs_nulas.xlsx")
        df.to_excel(ruta, sheet_name="BASE SIPSA_A", index=False)
        result = leer_base(ruta)
        assert result["Observaciones"].isna().all()

    def test_digitador_completamente_nulo_es_valido(self, tmp_path):
        """Digitador es null en el 100% de filas reales — debe aceptarse."""
        df = _base_real(5)
        df["Digitador"] = None
        ruta = str(tmp_path / "digitador_nulo.xlsx")
        df.to_excel(ruta, sheet_name="BASE SIPSA_A", index=False)
        result = leer_base(ruta)
        assert len(result) == 5


# ─── T10: pipeline integrado ─────────────────────────────────────────────────

class TestPipelineEndToEnd:
    def test_flujo_completo_produce_bronze_correcto(self, excel_valido):
        """leer_base produce el snapshot bronze con todos los datos intactos."""
        bronze = leer_base(excel_valido)
        assert len(bronze) == 30
        assert "Ali" in bronze.columns
        assert "Cant Kg" in bronze.columns
        assert "FechaEncuesta" in bronze.columns

    def test_tres_periodos_en_bronze(self, excel_valido):
        """El archivo de test tiene 3 meses — el bronze debe conservarlos."""
        bronze = leer_base(excel_valido)
        n_periodos = bronze["FechaEncuesta"].dt.to_period("M").nunique()
        assert n_periodos == 3

    def test_no_hay_perdida_de_filas(self, excel_valido):
        """El nodo no filtra filas — todas deben llegar al bronze."""
        bronze = leer_base(excel_valido)
        assert len(bronze) == 30
