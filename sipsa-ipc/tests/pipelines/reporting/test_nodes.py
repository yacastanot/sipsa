"""Tests unitarios y validación numérica — FASE 7: Generación de Reportes."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from sipsa_ipc.pipelines.reporting.nodes import (
    _fmt_pct,
    exportar_alimentos_priorizados,
    exportar_sipsa_ipc,
    guardar_historico,
)

# ─── fixtures ─────────────────────────────────────────────────────────────────

def _td_total_var() -> pd.DataFrame:
    filas = [
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ",
         "AbastTotal_MesActual": 22451.17, "AbastTotal_MesAnterior": 23183.75,
         "AbastTotal_AnoAnterior": 22842.12,
         "VariacMensual": "-3,159874912%", "VariacAnual": "-1,711500846%",
         "VariacMensual_num": -3.159874912, "VariacAnual_num": -1.711500846},
        {"RArtículo_IPC": 1019, "Artículo_IPC": "PAPA",
         "AbastTotal_MesActual": 89608.84, "AbastTotal_MesAnterior": 88629.56,
         "AbastTotal_AnoAnterior": 97851.96,
         "VariacMensual": "1,1049169149%", "VariacAnual": "-8,42406938%",
         "VariacMensual_num": 1.1049169149, "VariacAnual_num": -8.42406938},
    ]
    df = pd.DataFrame(filas)
    df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
    return df


def _td_abast() -> pd.DataFrame:
    filas = [
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ",
         "Departamento Proc.": "Tolima", "Sum_Ton": 5403.21,
         "Total_Artículo": 22451.17, "Participación": 24.07},
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ",
         "Departamento Proc.": "Meta", "Sum_Ton": 5188.65,
         "Total_Artículo": 22451.17, "Participación": 23.11},
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ",
         "Departamento Proc.": "N.A.", "Sum_Ton": 463.50,
         "Total_Artículo": 22451.17, "Participación": 2.06},
        {"RArtículo_IPC": 1019, "Artículo_IPC": "PAPA",
         "Departamento Proc.": "Boyacá", "Sum_Ton": 50000.0,
         "Total_Artículo": 89608.84, "Participación": 55.80},
    ]
    df = pd.DataFrame(filas)
    df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
    return df


def _td_destino() -> pd.DataFrame:
    filas = [
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ",
         "Ciudad": "Barranquilla", "Sum_Ton": 6620.33,
         "Total_Artículo": 22451.17, "Participación": 29.49},
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ",
         "Ciudad": "Medellín", "Sum_Ton": 6264.10,
         "Total_Artículo": 22451.17, "Participación": 27.90},
        {"RArtículo_IPC": 1019, "Artículo_IPC": "PAPA",
         "Ciudad": "Bogotá, D.C.", "Sum_Ton": 25869.64,
         "Total_Artículo": 89608.84, "Participación": 28.87},
    ]
    df = pd.DataFrame(filas)
    df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
    return df


def _td_otros() -> pd.DataFrame:
    filas = [
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ",
         "Municipio Proc.": "Ecuador", "Sum_Ton": 460.0,
         "Total_Artículo": 463.5, "Participación": 99.24},
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ",
         "Municipio Proc.": "Canadá", "Sum_Ton": 3.5,
         "Total_Artículo": 463.5, "Participación": 0.76},
    ]
    df = pd.DataFrame(filas)
    df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
    return df


# ─── _fmt_pct ─────────────────────────────────────────────────────────────────

class TestFmtPct:
    def test_coma_decimal(self):
        assert _fmt_pct(24.07) == "24,07%"

    def test_dos_decimales(self):
        assert _fmt_pct(5.5) == "5,50%"

    def test_cero(self):
        assert _fmt_pct(0.0) == "0,00%"

    def test_negativo(self):
        assert _fmt_pct(-3.14) == "-3,14%"


# ─── exportar_sipsa_ipc ───────────────────────────────────────────────────────

class TestExportarSipsaIpc:
    def test_archivo_creado(self, tmp_path):
        meta = exportar_sipsa_ipc(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "20250502", str(tmp_path)
        )
        assert Path(meta["archivo"].iloc[0]).exists()

    def test_nombre_correcto(self, tmp_path):
        meta = exportar_sipsa_ipc(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "20250502", str(tmp_path)
        )
        assert "SIPSA_IPC_20250502.xlsx" in meta["archivo"].iloc[0]

    def test_cuatro_hojas(self, tmp_path):
        exportar_sipsa_ipc(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "20250502", str(tmp_path)
        )
        xl = pd.ExcelFile(tmp_path / "SIPSA_IPC_20250502.xlsx")
        assert xl.sheet_names == ["TD_Total", "TD_Abast", "TD_Destino", "TD_Abast_Otros"]

    def test_td_total_sin_columnas_num(self, tmp_path):
        """VariacMensual_num y VariacAnual_num no deben aparecer en el Excel."""
        exportar_sipsa_ipc(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "20250502", str(tmp_path)
        )
        td = pd.read_excel(tmp_path / "SIPSA_IPC_20250502.xlsx", sheet_name="TD_Total")
        assert "VariacMensual_num" not in td.columns
        assert "VariacAnual_num" not in td.columns

    def test_td_total_columnas_correctas(self, tmp_path):
        exportar_sipsa_ipc(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "20250502", str(tmp_path)
        )
        td = pd.read_excel(tmp_path / "SIPSA_IPC_20250502.xlsx", sheet_name="TD_Total")
        assert list(td.columns) == [
            "RArtículo_IPC", "Artículo_IPC",
            "AbastTotal_MesActual", "AbastTotal_MesAnterior", "AbastTotal_AnoAnterior",
            "VariacMensual", "VariacAnual",
        ]

    def test_variacion_mensual_es_string_colombiano(self, tmp_path):
        """VariacMensual debe ser cadena con coma y porcentaje (no número)."""
        exportar_sipsa_ipc(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "20250502", str(tmp_path)
        )
        td = pd.read_excel(tmp_path / "SIPSA_IPC_20250502.xlsx", sheet_name="TD_Total")
        vm = td["VariacMensual"].iloc[0]
        assert isinstance(vm, str)
        assert "," in vm
        assert vm.endswith("%")

    def test_filas_td_abast(self, tmp_path):
        exportar_sipsa_ipc(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "20250502", str(tmp_path)
        )
        ta = pd.read_excel(tmp_path / "SIPSA_IPC_20250502.xlsx", sheet_name="TD_Abast")
        assert len(ta) == len(_td_abast())

    def test_metadata_correcta(self, tmp_path):
        meta = exportar_sipsa_ipc(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "20250502", str(tmp_path)
        )
        assert meta["hojas"].iloc[0] == 4
        assert meta["filas_td_total"].iloc[0] == 2
        assert meta["filas_td_abast"].iloc[0] == len(_td_abast())


# ─── exportar_alimentos_priorizados ───────────────────────────────────────────

class TestExportarAlimentosPriorizados:
    def test_archivo_creado(self, tmp_path):
        meta = exportar_alimentos_priorizados(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "Abril", 2025, "20250502", str(tmp_path)
        )
        assert Path(meta["archivo"].iloc[0]).exists()

    def test_nombre_contiene_mes(self, tmp_path):
        meta = exportar_alimentos_priorizados(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "Abril", 2025, "20250502", str(tmp_path)
        )
        assert "abr25" in meta["archivo"].iloc[0]

    def test_hoja_articulos_ipc(self, tmp_path):
        exportar_alimentos_priorizados(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "Abril", 2025, "20250502", str(tmp_path)
        )
        archivos = list(tmp_path.glob("Alimentos_priorizados_*.xlsx"))
        assert len(archivos) == 1
        xl = pd.read_excel(archivos[0], sheet_name="Artículos_IPC")
        assert "Zonas abastecedoras" in xl.columns
        assert "Destino de los alimentos" in xl.columns

    def test_zonas_contiene_formato_na(self, tmp_path):
        """Las importaciones deben aparecer como 'N.A. (Ecuador, Canadá)  x,xx%'."""
        exportar_alimentos_priorizados(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "Abril", 2025, "20250502", str(tmp_path)
        )
        archivos = list(tmp_path.glob("Alimentos_priorizados_*.xlsx"))
        xl = pd.read_excel(archivos[0], sheet_name="Artículos_IPC")
        arroz = xl.loc[xl["RArtículo_IPC"] == 1001, "Zonas abastecedoras"].iloc[0]
        assert "N.A." in arroz
        assert "Ecuador" in arroz

    def test_n_articulos_correcto(self, tmp_path):
        meta = exportar_alimentos_priorizados(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "Abril", 2025, "20250502", str(tmp_path)
        )
        assert meta["articulos"].iloc[0] == 2  # solo 2 artículos en fixture

    def test_variacion_es_numerica(self, tmp_path):
        """En Alimentos priorizados la variación se guarda como decimal, no string."""
        exportar_alimentos_priorizados(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "Abril", 2025, "20250502", str(tmp_path)
        )
        archivos = list(tmp_path.glob("Alimentos_priorizados_*.xlsx"))
        xl = pd.read_excel(archivos[0], sheet_name="Artículos_IPC")
        vm = xl["Variacion mensual"].iloc[0]
        assert isinstance(vm, float)


# ─── guardar_historico ────────────────────────────────────────────────────────

class TestGuardarHistorico:
    def test_columnas_mes_anio(self):
        resultado = guardar_historico(_td_total_var(), "Abril", 2025)
        assert "mes" in resultado.columns
        assert "anio" in resultado.columns

    def test_valores_mes_anio(self):
        resultado = guardar_historico(_td_total_var(), "Abril", 2025)
        assert (resultado["mes"] == "Abril").all()
        assert (resultado["anio"] == 2025).all()

    def test_columnas_td_total_preservadas(self):
        resultado = guardar_historico(_td_total_var(), "Abril", 2025)
        assert "RArtículo_IPC" in resultado.columns
        assert "VariacMensual" in resultado.columns
        assert "VariacMensual_num" in resultado.columns

    def test_filas_preservadas(self):
        fixture = _td_total_var()
        resultado = guardar_historico(fixture, "Abril", 2025)
        assert len(resultado) == len(fixture)


# ─── Validación numérica vs SAS (Tarea 41) ────────────────────────────────────

RUTA_REFERENCIA = (
    r"C:\Users\Jeferson\OneDrive - Cloud Integration Hub"
    r"\Documentos\DANE Automatización\SIPSA IPC"
    r"\2025\2025\02Salida\SIPSA_IPC_20250502.xlsx"
)


@pytest.mark.skipif(
    not __import__("pathlib").Path(RUTA_REFERENCIA).exists(),
    reason="Archivo de referencia SAS no disponible en esta máquina",
)
class TestValidacionNumerica:
    """Tarea 41 — Validación numérica outputs Python vs SAS (tolerancia < 0.01%)."""

    @pytest.fixture(scope="class")
    def datos_reales(self):
        """Carga los Parquets producidos por el pipeline completo."""
        return {
            "td_total": pd.read_parquet(
                "data/04_feature/td_total_variaciones.parquet"
            ),
            "td_abast": pd.read_parquet(
                "data/04_feature/td_abast_fmt.parquet"
            ),
            "td_destino": pd.read_parquet(
                "data/04_feature/td_destino_fmt.parquet"
            ),
            "td_otros": pd.read_parquet(
                "data/04_feature/td_abast_otros_fmt.parquet"
            ),
        }

    @pytest.fixture(scope="class")
    def datos_sas(self):
        return {
            hoja: pd.read_excel(RUTA_REFERENCIA, sheet_name=hoja)
            for hoja in ["TD_Total", "TD_Abast", "TD_Destino", "TD_Abast_Otros"]
        }

    def test_td_total_filas_identicas(self, datos_reales, datos_sas):
        assert len(datos_reales["td_total"]) == len(datos_sas["TD_Total"])

    def test_td_abast_filas_identicas(self, datos_reales, datos_sas):
        assert len(datos_reales["td_abast"]) == len(datos_sas["TD_Abast"])

    def test_td_destino_filas_identicas(self, datos_reales, datos_sas):
        assert len(datos_reales["td_destino"]) == len(datos_sas["TD_Destino"])

    def test_td_otros_filas_identicas(self, datos_reales, datos_sas):
        assert len(datos_reales["td_otros"]) == len(datos_sas["TD_Abast_Otros"])

    def test_abast_total_mes_actual_tolerancia(self, datos_reales, datos_sas):
        """AbastTotal_MesActual debe diferir < 0.01% del SAS."""
        py = datos_reales["td_total"].set_index("RArtículo_IPC")["AbastTotal_MesActual"]
        sas = datos_sas["TD_Total"].set_index("RArtículo_IPC")["AbastTotal_MesActual"]
        diff_pct = ((py - sas).abs() / sas * 100).max()
        assert diff_pct < 0.01, f"Diferencia máxima: {diff_pct:.6f}%"

    def test_sum_ton_td_abast_tolerancia(self, datos_reales, datos_sas):
        """Sum_Ton en TD_Abast por artículo debe diferir < 0.01%."""
        py_sum = datos_reales["td_abast"].groupby("RArtículo_IPC")["Sum_Ton"].sum()
        sas_sum = datos_sas["TD_Abast"].groupby("RArtículo_IPC")["Sum_Ton"].sum()
        diff = (py_sum - sas_sum).abs().max()
        assert diff < 0.01, f"Diferencia máxima Sum_Ton: {diff:.6f}"

    def test_participacion_td_abast_tolerancia(self, datos_reales, datos_sas):
        """Participación en TD_Abast debe ser idéntica al SAS (misma fórmula)."""
        py = datos_reales["td_abast"].set_index(
            ["RArtículo_IPC", "Departamento Proc."]
        )["Participación"]
        sas = datos_sas["TD_Abast"].set_index(
            ["RArtículo_IPC", "Departamento Proc."]
        )["Participación"]
        merged = py.to_frame("py").join(sas.to_frame("sas"), how="inner")
        diff = (merged["py"] - merged["sas"]).abs().max()
        assert diff < 0.01, f"Diferencia máxima Participación: {diff:.6f}"
