"""Tests unitarios y validación numérica — FASE 7: Generación de Reportes."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sipsa_abastecimiento.pipelines.reporting.nodes import (
    _fmt_pct,
    exportar_alimentos_priorizados,
    exportar_sipsa_abastecimiento,
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


def _articulos_ipc_fixture() -> dict:
    return {
        "codigos":    {"ARROZ": 1001, "PAPA": 1019},
        "variedades": {"Arroz": "ARROZ", "Papa parda pastusa": "PAPA"},
    }


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


# ─── exportar_sipsa_abastecimiento ───────────────────────────────────────────────────────

class TestExportarSipsaIpc:
    def test_archivo_creado(self, tmp_path):
        meta = exportar_sipsa_abastecimiento(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            _articulos_ipc_fixture(), "20250502", str(tmp_path),
        )
        assert Path(meta["archivo"].iloc[0]).exists()

    def test_nombre_correcto(self, tmp_path):
        meta = exportar_sipsa_abastecimiento(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            _articulos_ipc_fixture(), "20250502", str(tmp_path),
        )
        assert "SIPSA_ABASTECIMIENTO_20250502.xlsx" in meta["archivo"].iloc[0]

    def test_cinco_hojas(self, tmp_path):
        exportar_sipsa_abastecimiento(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            _articulos_ipc_fixture(), "20250502", str(tmp_path),
        )
        xl = pd.ExcelFile(tmp_path / "SIPSA_ABASTECIMIENTO_20250502.xlsx")
        assert xl.sheet_names == [
            "TD_Total", "TD_Abast", "TD_Destino", "TD_Abast_Otros", "TREF_Productos"
        ]

    def test_td_total_sin_columnas_num(self, tmp_path):
        """VariacMensual_num y VariacAnual_num no deben aparecer en TD_Total del T38."""
        exportar_sipsa_abastecimiento(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            _articulos_ipc_fixture(), "20250502", str(tmp_path),
        )
        td = pd.read_excel(tmp_path / "SIPSA_ABASTECIMIENTO_20250502.xlsx", sheet_name="TD_Total")
        assert "VariacMensual_num" not in td.columns
        assert "VariacAnual_num" not in td.columns

    def test_td_total_columnas_correctas(self, tmp_path):
        exportar_sipsa_abastecimiento(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            _articulos_ipc_fixture(), "20250502", str(tmp_path),
        )
        td = pd.read_excel(tmp_path / "SIPSA_ABASTECIMIENTO_20250502.xlsx", sheet_name="TD_Total")
        assert list(td.columns) == [
            "RArtículo_IPC", "Artículo_IPC",
            "AbastTotal_MesActual", "AbastTotal_MesAnterior", "AbastTotal_AnoAnterior",
            "VariacMensual", "VariacAnual",
        ]

    def test_variacion_mensual_es_string_colombiano(self, tmp_path):
        """VariacMensual en T38 TD_Total mantiene formato string (compatibilidad SAS)."""
        exportar_sipsa_abastecimiento(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            _articulos_ipc_fixture(), "20250502", str(tmp_path),
        )
        td = pd.read_excel(tmp_path / "SIPSA_ABASTECIMIENTO_20250502.xlsx", sheet_name="TD_Total")
        vm = td["VariacMensual"].iloc[0]
        assert isinstance(vm, str)
        assert "," in vm
        assert vm.endswith("%")

    def test_td_abast_tiene_descr_pegar(self, tmp_path):
        """TD_Abast debe incluir la columna Descr_pegar (col 9) para FORMATO_SIPSA_IPC.xlsm."""
        exportar_sipsa_abastecimiento(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            _articulos_ipc_fixture(), "20250502", str(tmp_path),
        )
        ta = pd.read_excel(tmp_path / "SIPSA_ABASTECIMIENTO_20250502.xlsx", sheet_name="TD_Abast")
        assert "Descr_pegar" in ta.columns
        assert "Proc_Part" in ta.columns
        # Descr_pegar es la col 9 (0-indexed 8) — la que usa el macro VBA
        assert list(ta.columns).index("Descr_pegar") == 8

    def test_td_abast_descr_pegar_multilinea(self, tmp_path):
        """Descr_pegar agrupa todos los departamentos del artículo."""
        exportar_sipsa_abastecimiento(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            _articulos_ipc_fixture(), "20250502", str(tmp_path),
        )
        ta = pd.read_excel(tmp_path / "SIPSA_ABASTECIMIENTO_20250502.xlsx", sheet_name="TD_Abast")
        arroz = ta.loc[ta["RArtículo_IPC"] == 1001, "Descr_pegar"].iloc[0]
        assert "Tolima" in arroz
        assert "Meta" in arroz
        assert "N.A." in arroz
        assert "\n" in arroz

    def test_td_destino_tiene_descr_pegar(self, tmp_path):
        """TD_Destino debe incluir la columna Descr_pegar (col 8) para FORMATO_SIPSA_IPC.xlsm."""
        exportar_sipsa_abastecimiento(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            _articulos_ipc_fixture(), "20250502", str(tmp_path),
        )
        td = pd.read_excel(tmp_path / "SIPSA_ABASTECIMIENTO_20250502.xlsx", sheet_name="TD_Destino")
        assert "Descr_pegar" in td.columns
        assert "Ciudad_Part" in td.columns
        assert list(td.columns).index("Descr_pegar") == 7

    def test_tref_productos_generado(self, tmp_path):
        exportar_sipsa_abastecimiento(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            _articulos_ipc_fixture(), "20250502", str(tmp_path),
        )
        tref = pd.read_excel(tmp_path / "SIPSA_ABASTECIMIENTO_20250502.xlsx", sheet_name="TREF_Productos")
        assert "Código SIPSA" in tref.columns
        assert "Artículo IPC" in tref.columns
        assert len(tref) == 2  # ARROZ y PAPA

    def test_filas_td_abast(self, tmp_path):
        exportar_sipsa_abastecimiento(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            _articulos_ipc_fixture(), "20250502", str(tmp_path),
        )
        ta = pd.read_excel(tmp_path / "SIPSA_ABASTECIMIENTO_20250502.xlsx", sheet_name="TD_Abast")
        assert len(ta) == len(_td_abast())

    def test_metadata_correcta(self, tmp_path):
        meta = exportar_sipsa_abastecimiento(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            _articulos_ipc_fixture(), "20250502", str(tmp_path),
        )
        assert meta["hojas"].iloc[0] == 5  # 4 TD + TREF_Productos
        assert meta["filas_td_total"].iloc[0] == 2
        assert meta["filas_td_abast"].iloc[0] == len(_td_abast())


# ─── exportar_alimentos_priorizados ───────────────────────────────────────────

class TestExportarAlimentosPriorizados:
    """T39 — output idéntico al macro 'PEGAR DATOS' de FORMATO_SIPSA_IPC.xlsm."""

    def _run(self, tmp_path):
        """Helper: ejecuta el nodo y retorna (meta, df)."""
        meta = exportar_alimentos_priorizados(
            _td_total_var(), _td_abast(), _td_destino(), _td_otros(),
            "Abril", 2025, "20250502", str(tmp_path),
            # sin archivo_entrada → usa plantilla vacía con headers por defecto
        )
        archivos = list(tmp_path.glob("Alimentos_priorizados_*.xlsx"))
        xl = pd.read_excel(archivos[0], sheet_name="Artículos_IPC", header=1)
        return meta, xl

    def test_archivo_creado(self, tmp_path):
        meta, _ = self._run(tmp_path)
        assert Path(meta["archivo"].iloc[0]).exists()

    def test_nombre_contiene_mes(self, tmp_path):
        meta, _ = self._run(tmp_path)
        assert "abr25" in meta["archivo"].iloc[0]

    def test_18_columnas(self, tmp_path):
        """La hoja Artículos_IPC debe tener exactamente 18 columnas."""
        _, xl = self._run(tmp_path)
        assert xl.shape[1] == 18

    def test_fila_vacia_en_row1(self, tmp_path):
        """Fila 1 del Excel debe estar vacía (estructura idéntica al XLSM)."""
        meta, _ = self._run(tmp_path)
        archivos = list(tmp_path.parent.glob("Alimentos_priorizados_*.xlsx"))
        # Leer SIN header para ver row 0
        xl_raw = pd.read_excel(archivos[0] if archivos else Path(meta["archivo"].iloc[0]),
                               sheet_name="Artículos_IPC", header=None)
        assert xl_raw.iloc[0].isna().all(), "Fila 1 debe estar completamente vacía"

    def test_codigo_en_col_a(self, tmp_path):
        """Código IPC debe estar en col A (posición 0), igual que el XLSM."""
        _, xl = self._run(tmp_path)
        # col A tiene header None; acceder por posición
        col_a = xl.iloc[:, 0]
        assert col_a.notna().all(), "Col A no debe tener nulos (debe tener código IPC)"
        assert set(col_a.astype(int).tolist()).issubset({1001, 1019})

    def test_zonas_abastecedoras_rellenas(self, tmp_path):
        """Col I (posición 8) = Zonas abastecedoras, con texto multilinea."""
        _, xl = self._run(tmp_path)
        zonas = xl.iloc[:, 8]
        assert zonas.notna().any()
        # ARROZ tiene Tolima y Meta
        arroz_zonas = xl.iloc[:, 8].iloc[0]  # primer artículo (código 1001)
        assert "Tolima" in str(arroz_zonas)
        assert "Meta" in str(arroz_zonas)

    def test_zonas_contiene_formato_na(self, tmp_path):
        """Las importaciones deben aparecer como 'N.A. (Ecuador, Canadá)  x,xx%'."""
        _, xl = self._run(tmp_path)
        # Buscar artículo con código 1001 (ARROZ) — col A posición 0
        mask = xl.iloc[:, 0].astype(int) == 1001
        arroz_zonas = xl.loc[mask].iloc[:, 8].iloc[0]
        assert "N.A." in str(arroz_zonas)
        assert "Ecuador" in str(arroz_zonas)

    def test_destino_relleno(self, tmp_path):
        """Col K (posición 10) = Destino de los alimentos, con texto multilinea."""
        _, xl = self._run(tmp_path)
        destino = xl.iloc[:, 10]
        assert destino.notna().any()
        arroz_destino = xl.iloc[:, 10].iloc[0]
        assert "Barranquilla" in str(arroz_destino)

    def test_variacion_mensual_es_numerica(self, tmp_path):
        """Col O (posición 14) = variación mensual como decimal numérico (no string)."""
        _, xl = self._run(tmp_path)
        vm = xl.iloc[:, 14].iloc[0]
        assert isinstance(vm, float), f"Se esperaba float, se obtuvo {type(vm)}: {vm!r}"

    def test_variacion_anual_es_numerica(self, tmp_path):
        """Col P (posición 15) = variación anual como decimal numérico."""
        _, xl = self._run(tmp_path)
        va = xl.iloc[:, 15].iloc[0]
        assert isinstance(va, float), f"Se esperaba float, se obtuvo {type(va)}: {va!r}"

    def test_abastecimiento_act_numerico(self, tmp_path):
        """Col L (posición 11) = abastecimiento mes actual como número."""
        _, xl = self._run(tmp_path)
        abast = xl.iloc[:, 11].iloc[0]
        assert isinstance(abast, float)
        assert abast > 0

    def test_n_articulos_correcto(self, tmp_path):
        meta, _ = self._run(tmp_path)
        assert meta["articulos"].iloc[0] == 2

    def test_col_b_vacia(self, tmp_path):
        """Col B (posición 1, 'Código SIPSA') debe estar vacía — igual que el XLSM."""
        _, xl = self._run(tmp_path)
        col_b = xl.iloc[:, 1]
        assert col_b.isna().all(), "Col B 'Código SIPSA' debe estar vacía en el output"


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


# ─── Validación numérica vs SAS ───────────────────────────────────────────────

RUTA_REFERENCIA = (
    r"C:\Users\Jeferson\OneDrive - Cloud Integration Hub"
    r"\Documentos\DANE Automatización\SIPSA IPC"
    r"\2025\2025\02Salida\SIPSA_ABASTECIMIENTO_20250502.xlsx"
)


@pytest.mark.skipif(
    not __import__("pathlib").Path(RUTA_REFERENCIA).exists(),
    reason="Archivo de referencia SAS no disponible en esta máquina",
)
class TestValidacionNumerica:
    """Validación numérica outputs Python vs SAS (tolerancia < 0.01%)."""

    @pytest.fixture(scope="class")
    def datos_reales(self):
        return {
            "td_total":  pd.read_parquet("data/04_feature/td_total_variaciones.parquet"),
            "td_abast":  pd.read_parquet("data/04_feature/td_abast_fmt.parquet"),
            "td_destino":pd.read_parquet("data/04_feature/td_destino_fmt.parquet"),
            "td_otros":  pd.read_parquet("data/04_feature/td_abast_otros_fmt.parquet"),
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
        py  = datos_reales["td_total"].set_index("RArtículo_IPC")["AbastTotal_MesActual"]
        sas = datos_sas["TD_Total"].set_index("RArtículo_IPC")["AbastTotal_MesActual"]
        diff_pct = ((py - sas).abs() / sas * 100).max()
        assert diff_pct < 0.01, f"Diferencia máxima: {diff_pct:.6f}%"

    def test_sum_ton_td_abast_tolerancia(self, datos_reales, datos_sas):
        py_sum  = datos_reales["td_abast"].groupby("RArtículo_IPC")["Sum_Ton"].sum()
        sas_sum = datos_sas["TD_Abast"].groupby("RArtículo_IPC")["Sum_Ton"].sum()
        diff    = (py_sum - sas_sum).abs().max()
        assert diff < 0.01, f"Diferencia máxima Sum_Ton: {diff:.6f}"

    def test_participacion_td_abast_tolerancia(self, datos_reales, datos_sas):
        py  = datos_reales["td_abast"].set_index(
            ["RArtículo_IPC", "Departamento Proc."]
        )["Participación"]
        sas = datos_sas["TD_Abast"].set_index(
            ["RArtículo_IPC", "Departamento Proc."]
        )["Participación"]
        merged = py.to_frame("py").join(sas.to_frame("sas"), how="inner")
        diff   = (merged["py"] - merged["sas"]).abs().max()
        assert diff < 0.01, f"Diferencia máxima Participación: {diff:.6f}"
