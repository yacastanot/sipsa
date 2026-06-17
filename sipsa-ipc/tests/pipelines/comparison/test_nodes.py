"""Tests unitarios — FASE 5: Análisis Comparativo Interperiódico."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from sipsa_abastecimiento.pipelines.comparison.nodes import (
    _formatear_variacion,
    _variacion_pct,
    calcular_variaciones,
)

# ─── fixture ──────────────────────────────────────────────────────────────────

# Valores reales del Excel de referencia SAS — abril 2025 (sipsa_abastecimiento_20250502.xlsx)
# para los primeros 3 artículos. Permite validación numérica exacta.
REFERENCIA_SAS = [
    {
        "RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ",
        "AbastTotal_MesActual": 22451.17250,
        "AbastTotal_MesAnterior": 23183.7500,
        "AbastTotal_AnoAnterior": 22842.11550,
        "VariacMensual_sas": "-3,159874912%",
        "VariacAnual_sas": "-1,711500846%",
    },
    {
        "RArtículo_IPC": 1007, "Artículo_IPC": "HUEVOS",
        "AbastTotal_MesActual": 2214.48692,
        "AbastTotal_MesAnterior": 2051.0760,
        "AbastTotal_AnoAnterior": 2222.20368,
        "VariacMensual_sas": "7,9670826435%",
        "VariacAnual_sas": "-0,347257098%",
    },
    {
        "RArtículo_IPC": 1012, "Artículo_IPC": "MANGO",
        "AbastTotal_MesActual": 13769.48400,
        "AbastTotal_MesAnterior": 11516.0550,
        "AbastTotal_AnoAnterior": 13691.43800,
        "VariacMensual_sas": "19,567716549%",
        "VariacAnual_sas": "0,5700350832%",
    },
    {
        "RArtículo_IPC": 1029, "Artículo_IPC": "CILANTRO",
        "AbastTotal_MesActual": 2804.58000,
        "AbastTotal_MesAnterior": 2551.4900,
        "AbastTotal_AnoAnterior": 2351.85900,
        "VariacMensual_sas": "9,9193020549%",
        "VariacAnual_sas": "19,249495824%",
    },
]


def _td_total_fixture() -> pd.DataFrame:
    filas = [
        {
            "RArtículo_IPC": r["RArtículo_IPC"],
            "Artículo_IPC": r["Artículo_IPC"],
            "AbastTotal_MesActual": r["AbastTotal_MesActual"],
            "AbastTotal_MesAnterior": r["AbastTotal_MesAnterior"],
            "AbastTotal_AnoAnterior": r["AbastTotal_AnoAnterior"],
        }
        for r in REFERENCIA_SAS
    ]
    df = pd.DataFrame(filas)
    df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
    return df


# ─── _formatear_variacion ─────────────────────────────────────────────────────

class TestFormatearVariacion:
    def test_coma_como_decimal(self):
        resultado = _formatear_variacion(-3.159874912)
        assert "," in resultado
        assert "." not in resultado

    def test_termina_con_porcentaje(self):
        assert _formatear_variacion(5.0).endswith("%")

    def test_nan_devuelve_vacio(self):
        assert _formatear_variacion(float("nan")) == ""

    def test_inf_devuelve_vacio(self):
        assert _formatear_variacion(float("inf")) == ""

    def test_none_devuelve_vacio(self):
        assert _formatear_variacion(None) == ""

    def test_valor_positivo(self):
        resultado = _formatear_variacion(19.567716549)
        assert resultado.startswith("19,")

    def test_valor_negativo(self):
        resultado = _formatear_variacion(-3.159874912)
        assert resultado.startswith("-3,")

    def test_valor_cero(self):
        assert _formatear_variacion(0.0) == "0%"

    def test_sin_ceros_finales(self):
        # 5.50000 → "5,5%" no "5,50%"
        resultado = _formatear_variacion(5.5)
        assert resultado == "5,5%"


# ─── _variacion_pct ───────────────────────────────────────────────────────────

class TestVariacionPct:
    def test_calculo_correcto(self):
        actual = pd.Series([110.0])
        base = pd.Series([100.0])
        resultado = _variacion_pct(actual, base)
        assert resultado.iloc[0] == pytest.approx(10.0)

    def test_variacion_negativa(self):
        actual = pd.Series([90.0])
        base = pd.Series([100.0])
        resultado = _variacion_pct(actual, base)
        assert resultado.iloc[0] == pytest.approx(-10.0)

    def test_base_cero_produce_nan(self):
        actual = pd.Series([50.0])
        base = pd.Series([0.0])
        resultado = _variacion_pct(actual, base)
        assert pd.isna(resultado.iloc[0])

    def test_base_nan_produce_nan(self):
        actual = pd.Series([50.0])
        base = pd.Series([float("nan")])
        resultado = _variacion_pct(actual, base)
        assert pd.isna(resultado.iloc[0])


# ─── calcular_variaciones ─────────────────────────────────────────────────────

class TestCalcularVariaciones:
    def test_columnas_requeridas(self):
        df = calcular_variaciones(_td_total_fixture())
        assert {"VariacMensual", "VariacAnual",
                "VariacMensual_num", "VariacAnual_num"}.issubset(df.columns)

    def test_columnas_f4_preservadas(self):
        df = calcular_variaciones(_td_total_fixture())
        assert {"RArtículo_IPC", "Artículo_IPC",
                "AbastTotal_MesActual", "AbastTotal_MesAnterior",
                "AbastTotal_AnoAnterior"}.issubset(df.columns)

    def test_n_filas_preservadas(self):
        fixture = _td_total_fixture()
        resultado = calcular_variaciones(fixture)
        assert len(resultado) == len(fixture)

    @pytest.mark.parametrize("ref", REFERENCIA_SAS)
    def test_variacion_mensual_numerica(self, ref):
        """Comprueba que VariacMensual_num coincide con el cálculo esperado."""
        df = calcular_variaciones(_td_total_fixture())
        fila = df.loc[df["RArtículo_IPC"].eq(ref["RArtículo_IPC"])].iloc[0]
        esperado = (
            (ref["AbastTotal_MesActual"] - ref["AbastTotal_MesAnterior"])
            / ref["AbastTotal_MesAnterior"] * 100
        )
        assert fila["VariacMensual_num"] == pytest.approx(esperado, rel=1e-10)

    @pytest.mark.parametrize("ref", REFERENCIA_SAS)
    def test_variacion_anual_numerica(self, ref):
        """Comprueba que VariacAnual_num coincide con el cálculo esperado."""
        df = calcular_variaciones(_td_total_fixture())
        fila = df.loc[df["RArtículo_IPC"].eq(ref["RArtículo_IPC"])].iloc[0]
        esperado = (
            (ref["AbastTotal_MesActual"] - ref["AbastTotal_AnoAnterior"])
            / ref["AbastTotal_AnoAnterior"] * 100
        )
        assert fila["VariacAnual_num"] == pytest.approx(esperado, rel=1e-10)

    @pytest.mark.parametrize("ref", REFERENCIA_SAS)
    def test_variacion_mensual_formato_colombiano(self, ref):
        """Comprueba que VariacMensual use coma y termine en %."""
        df = calcular_variaciones(_td_total_fixture())
        fila = df.loc[df["RArtículo_IPC"].eq(ref["RArtículo_IPC"])].iloc[0]
        vm = fila["VariacMensual"]
        assert "." not in vm, f"Punto decimal no reemplazado: {vm!r}"
        assert vm.endswith("%"), f"Falta símbolo %: {vm!r}"
        assert "," in vm or vm == "0%", f"Falta coma decimal: {vm!r}"

    @pytest.mark.parametrize("ref", REFERENCIA_SAS)
    def test_variacion_mensual_coincide_sas(self, ref):
        """Validación numérica contra el Excel SAS de referencia (abril 2025).

        Convierte la cadena SAS a float para comparar con independencia del
        número exacto de dígitos mostrados.
        """
        df = calcular_variaciones(_td_total_fixture())
        fila = df.loc[df["RArtículo_IPC"].eq(ref["RArtículo_IPC"])].iloc[0]
        # Convierte coma→punto para parsear como float
        vm_python = float(fila["VariacMensual"].replace("%", "").replace(",", "."))
        vm_sas = float(ref["VariacMensual_sas"].replace("%", "").replace(",", "."))
        assert vm_python == pytest.approx(vm_sas, rel=1e-6)

    @pytest.mark.parametrize("ref", REFERENCIA_SAS)
    def test_variacion_anual_coincide_sas(self, ref):
        """Validación numérica contra el Excel SAS de referencia (abril 2025)."""
        df = calcular_variaciones(_td_total_fixture())
        fila = df.loc[df["RArtículo_IPC"].eq(ref["RArtículo_IPC"])].iloc[0]
        va_python = float(fila["VariacAnual"].replace("%", "").replace(",", "."))
        va_sas = float(ref["VariacAnual_sas"].replace("%", "").replace(",", "."))
        assert va_python == pytest.approx(va_sas, rel=1e-6)

    def test_articulo_sin_mes_anterior_nan(self):
        """Si no hay MesAnterior, VariacMensual debe ser NaN y cadena vacía."""
        df = pd.DataFrame([{
            "RArtículo_IPC": 9999, "Artículo_IPC": "TEST",
            "AbastTotal_MesActual": 100.0,
            "AbastTotal_MesAnterior": None,
            "AbastTotal_AnoAnterior": 90.0,
        }])
        df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
        resultado = calcular_variaciones(df)
        assert pd.isna(resultado["VariacMensual_num"].iloc[0])
        assert resultado["VariacMensual"].iloc[0] == ""
