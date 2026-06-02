"""Pruebas unitarias para el pipeline union_ra.

Verifica la migración del script SAS 'UnirBase F2026_01C2026_01.sas':
  - acumular_fuentes:         concat + sort + control de fuentes activas
  - exportar_base_acumulada:  nombre dinámico del archivo (patrón F{anof}{mesf}C{anoc}{mesc})
  - Validaciones:             histórico vacío, fuentes faltantes, resultado vacío
"""
from __future__ import annotations

import os
import pytest
import pandas as pd

from emces.utils import ORDEN_FINAL_RA
from emces.pipelines.union_ra.nodes import acumular_fuentes, exportar_base_acumulada


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _df_ra(periodo_mes: str, flujo: str, n: int = 2) -> pd.DataFrame:
    """DataFrame mínimo alineado al schema RA para pruebas."""
    df = pd.DataFrame({col: [""] * n for col in ORDEN_FINAL_RA})
    df["periodo_mes"] = periodo_mes
    df["flujo_comercial"] = flujo
    df["total_en_dolares"] = [100.0, 200.0][:n]
    df["total_en_miles_de_pesos"] = [400_000.0, 800_000.0][:n]
    df["pais"] = [170, 250][:n]
    df["mes"] = periodo_mes.split("_")[1] if "_" in periodo_mes else "01"
    df["periodo"] = periodo_mes.split("_")[0] if "_" in periodo_mes else "2026"
    df["descripcion_cabps"] = ["DEVENGADOS"] * n
    return df


@pytest.fixture()
def ra_historico():
    """Simula la base histórica (todos los meses anteriores al corriente)."""
    meses_previos = ["2025_10", "2025_11", "2025_12"]
    partes = [_df_ra(pm, "IMPORTACIONES FLETES") for pm in meses_previos]
    return pd.concat(partes, ignore_index=True)


@pytest.fixture()
def fletes_maestro():
    return _df_ra("2026_01", "IMPORTACIONES FLETES")


@pytest.fixture()
def canc_maestro():
    return _df_ra("2026_01", "IMPORTACIONES GASTOS DEL GOBIERNO")


@pytest.fixture()
def fuentes_solo_fletes():
    return {"fletes": True, "cancilleria": False}


@pytest.fixture()
def fuentes_completas():
    return {"fletes": True, "cancilleria": True}


# ─── Tests: acumular_fuentes ──────────────────────────────────────────────────

class TestAcumularFuentes:
    def test_agrega_fletes_al_historico(self, ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes):
        resultado = acumular_fuentes(ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes)
        assert len(resultado) == len(ra_historico) + len(fletes_maestro)

    def test_agrega_fletes_y_cancilleria(self, ra_historico, fletes_maestro, canc_maestro, fuentes_completas):
        resultado = acumular_fuentes(ra_historico, fletes_maestro, canc_maestro, fuentes_completas)
        assert len(resultado) == len(ra_historico) + len(fletes_maestro) + len(canc_maestro)

    def test_cancilleria_inactiva_no_se_incluye(self, ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes):
        resultado = acumular_fuentes(ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes)
        flujos = resultado["flujo_comercial"].unique()
        assert "IMPORTACIONES GASTOS DEL GOBIERNO" not in flujos

    def test_ordenado_por_periodo_mes(self, ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes):
        """PROC SORT DATA=RA_1; BY PERIODO_MES → valores en orden ascendente."""
        resultado = acumular_fuentes(ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes)
        periodos = resultado["periodo_mes"].tolist()
        # Ignora NaN para la comparación de orden
        periodos_validos = [p for p in periodos if p and str(p) != "nan" and str(p) != ""]
        assert periodos_validos == sorted(periodos_validos), "No está ordenado por periodo_mes"

    def test_schema_canónico_preservado(self, ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes):
        resultado = acumular_fuentes(ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes)
        assert list(resultado.columns) == ORDEN_FINAL_RA

    def test_periodos_previos_conservados(self, ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes):
        """Los meses históricos no se pierden tras la acumulación."""
        resultado = acumular_fuentes(ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes)
        periodos = resultado["periodo_mes"].unique()
        for pm in ["2025_10", "2025_11", "2025_12", "2026_01"]:
            assert pm in periodos, f"Periodo {pm} faltante en el resultado"

    def test_error_historico_vacio(self, fletes_maestro, canc_maestro, fuentes_solo_fletes):
        df_vacio = pd.DataFrame(columns=ORDEN_FINAL_RA)
        with pytest.raises(ValueError, match="base histórica.*vacía"):
            acumular_fuentes(df_vacio, fletes_maestro, canc_maestro, fuentes_solo_fletes)

    def test_fletes_inactivo(self, ra_historico, fletes_maestro, canc_maestro):
        """Si fletes=False, solo queda el histórico sin datos nuevos."""
        fuentes = {"fletes": False, "cancilleria": False}
        resultado = acumular_fuentes(ra_historico, fletes_maestro, canc_maestro, fuentes)
        assert len(resultado) == len(ra_historico)

    def test_reset_index_limpio(self, ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes):
        resultado = acumular_fuentes(ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes)
        assert list(resultado.index) == list(range(len(resultado)))


# ─── Tests: exportar_base_acumulada ──────────────────────────────────────────

class TestExportarBaseAcumulada:
    @pytest.fixture()
    def base_acumulada(self, ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes):
        return acumular_fuentes(ra_historico, fletes_maestro, canc_maestro, fuentes_solo_fletes)

    def test_nombre_archivo_patron_sas(self, tmp_path, base_acumulada):
        """El nombre de salida replica el patrón del SAS: F{ANOF}{MESF}C{ANOC}{MESC}.xlsx"""
        metadata = exportar_base_acumulada(
            base_acumulada,
            ruta_salida=str(tmp_path),
            prefijo_salida="BaseEMCES-RA_2022-1",
            anof="26", mesf="01",
            anoc="26", mesc="01",
            hoja_salida="RA",
        )
        assert metadata["nombre_archivo"] == "BaseEMCES-RA_2022-1_F2601C2601.xlsx"

    def test_archivo_creado(self, tmp_path, base_acumulada):
        metadata = exportar_base_acumulada(
            base_acumulada, str(tmp_path),
            "BaseEMCES-RA_2022-1", "26", "01", "26", "01", "RA",
        )
        assert os.path.exists(metadata["ruta"])

    def test_metadata_correcta(self, tmp_path, base_acumulada):
        metadata = exportar_base_acumulada(
            base_acumulada, str(tmp_path),
            "BaseEMCES-RA_2022-1", "26", "01", "26", "01", "RA",
        )
        assert metadata["filas"] == len(base_acumulada)
        assert metadata["hoja"] == "RA"
        assert metadata["anof"] == "26"
        assert metadata["mesc"] == "01"

    def test_excel_legible(self, tmp_path, base_acumulada):
        """El Excel exportado debe ser legible con pandas y tener el mismo número de filas."""
        metadata = exportar_base_acumulada(
            base_acumulada, str(tmp_path),
            "BaseEMCES-RA_2022-1", "26", "01", "26", "01", "RA",
        )
        df_leido = pd.read_excel(metadata["ruta"], sheet_name="RA")
        assert len(df_leido) == len(base_acumulada)

    def test_prefijo_distinto(self, tmp_path, base_acumulada):
        """El prefijo se aplica correctamente al nombre del archivo."""
        metadata = exportar_base_acumulada(
            base_acumulada, str(tmp_path),
            "BaseEMCES-Prueba_2022-2", "25", "12", "26", "01", "RA",
        )
        assert metadata["nombre_archivo"] == "BaseEMCES-Prueba_2022-2_F2512C2601.xlsx"

    def test_error_resultado_vacio(self, tmp_path):
        df_vacio = pd.DataFrame(columns=ORDEN_FINAL_RA)
        with pytest.raises(ValueError, match="vacía"):
            exportar_base_acumulada(
                df_vacio, str(tmp_path),
                "BaseEMCES-RA_2022-1", "26", "01", "26", "01", "RA",
            )

    def test_periodos_en_metadata(self, tmp_path, base_acumulada):
        metadata = exportar_base_acumulada(
            base_acumulada, str(tmp_path),
            "BaseEMCES-RA_2022-1", "26", "01", "26", "01", "RA",
        )
        assert "2026_01" in metadata["periodos"]
        assert "2025_12" in metadata["periodos"]
