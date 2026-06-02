"""Pruebas unitarias para el pipeline de consolidación RA.

Verifica que la 'Función RA: Consolidación bases RA EMCES' (diagrama de flujo):
  - Une correctamente Fletes + Cancillería en la Base RA.
  - Alinea ambas fuentes al schema ORDEN_FINAL_RA.
  - Maneja diferencias de schema entre fuentes (ej. idtipodo solo en Cancillería).
  - Genera el resumen estadístico correctamente.
  - Falla limpiamente con mensajes útiles cuando hay problemas.
"""
from __future__ import annotations

import pytest
import pandas as pd

from emces.utils import ORDEN_FINAL_RA
from emces.pipelines.consolidacion_ra.nodes import consolidar_ra, generar_resumen_ra


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _df_minimo(flujo: str, n: int = 2) -> pd.DataFrame:
    """Crea un DataFrame mínimo válido para pruebas de consolidación."""
    return pd.DataFrame({
        "flujo_comercial": [flujo] * n,
        "idnoremp": ["777-1"] * n,
        "periodo": ["2026"] * n,
        "mes": ["01"] * n,
        "periodo_mes": ["2026_01"] * n,
        "pais": [170, 250][:n],
        "nombre_pais": ["Colombia", "Francia"][:n],
        "descripcion_cabps": ["DEVENGADOS"] * n,
        "total_en_dolares": [100.0, 200.0][:n],
        "total_en_miles_de_pesos": [400_000.0, 800_000.0][:n],
        "trm_base": [4000.0, 4000.0][:n],
        "modo": [1, 2][:n],
    })


@pytest.fixture()
def df_fletes():
    """Simula la salida de fletes_maestro — sin idtipodo."""
    df = _df_minimo("IMPORTACIONES FLETES")
    # Fletes NO tiene idtipodo (diferencia de schema con cancillería)
    assert "idtipodo" not in df.columns
    return df


@pytest.fixture()
def df_cancilleria():
    """Simula la salida de canc_maestro — con idtipodo."""
    df = _df_minimo("IMPORTACIONES GASTOS DEL GOBIERNO")
    df["idtipodo"] = " "  # cancillería sí lo tiene
    return df


@pytest.fixture()
def base_ra(df_fletes, df_cancilleria):
    return consolidar_ra(df_fletes, df_cancilleria)


# ─── Tests: consolidar_ra ─────────────────────────────────────────────────────

class TestConsolidarRa:
    def test_concatena_filas(self, df_fletes, df_cancilleria, base_ra):
        assert len(base_ra) == len(df_fletes) + len(df_cancilleria)

    def test_schema_canónico(self, base_ra):
        """Todas las columnas del schema RA deben estar presentes."""
        assert list(base_ra.columns) == ORDEN_FINAL_RA

    def test_ambas_fuentes_representadas(self, base_ra):
        flujos = set(base_ra["flujo_comercial"].unique())
        assert "IMPORTACIONES FLETES" in flujos
        assert "IMPORTACIONES GASTOS DEL GOBIERNO" in flujos

    def test_idtipodo_en_fletes_queda_vacio(self, df_fletes, df_cancilleria):
        """Fletes no tiene idtipodo — debe quedar "" tras la alineación."""
        base_ra = consolidar_ra(df_fletes, df_cancilleria)
        filas_fletes = base_ra[base_ra["flujo_comercial"] == "IMPORTACIONES FLETES"]
        assert (filas_fletes["idtipodo"] == "").all()

    def test_columnas_extra_en_fuente_se_descartan(self, df_cancilleria):
        """Columnas que no están en ORDEN_FINAL_RA deben descartarse."""
        df_fletes_extra = _df_minimo("IMPORTACIONES FLETES")
        df_fletes_extra["columna_extra_inventada"] = "X"
        base_ra = consolidar_ra(df_fletes_extra, df_cancilleria)
        assert "columna_extra_inventada" not in base_ra.columns

    def test_error_si_faltan_columnas_minimas(self, df_cancilleria):
        df_incompleto = pd.DataFrame({"flujo_comercial": ["FLETES"], "periodo": ["2026"]})
        with pytest.raises(ValueError, match="Columnas faltantes"):
            consolidar_ra(df_incompleto, df_cancilleria)

    def test_error_si_ambas_fuentes_vacias(self):
        df_vacio = pd.DataFrame(columns=ORDEN_FINAL_RA)
        # No pasa _COLS_MINIMAS_RA, así que lanza ValueError en validar_columnas
        with pytest.raises(ValueError):
            consolidar_ra(df_vacio, df_vacio)

    def test_periodo_mes_preservado(self, base_ra):
        assert "2026_01" in base_ra["periodo_mes"].values

    def test_tipos_numericos_preservados(self, base_ra):
        """Las columnas numéricas no se convierten a string durante la alineación."""
        fletes_rows = base_ra[base_ra["flujo_comercial"] == "IMPORTACIONES FLETES"]
        assert pd.to_numeric(fletes_rows["total_en_dolares"], errors="coerce").notna().all()


# ─── Tests: generar_resumen_ra ────────────────────────────────────────────────

class TestGenerarResumenRa:
    def test_estructura_del_resumen(self, base_ra):
        resumen = generar_resumen_ra(base_ra)
        for clave in ["total_filas", "periodo_mes", "flujos", "paises_distintos",
                      "sum_total_en_dolares", "sum_total_en_miles_de_pesos"]:
            assert clave in resumen

    def test_total_filas(self, base_ra):
        resumen = generar_resumen_ra(base_ra)
        assert resumen["total_filas"] == len(base_ra)

    def test_suma_dolares(self, df_fletes, df_cancilleria):
        base_ra = consolidar_ra(df_fletes, df_cancilleria)
        resumen = generar_resumen_ra(base_ra)
        expected = (
            df_fletes["total_en_dolares"].sum()
            + df_cancilleria["total_en_dolares"].sum()
        )
        assert abs(resumen["sum_total_en_dolares"] - expected) < 0.01

    def test_paises_distintos(self, base_ra):
        resumen = generar_resumen_ra(base_ra)
        # Los fixtures tienen pais 170 y 250 = 2 distintos en cada fuente
        assert resumen["paises_distintos"] >= 1


# ─── Tests: utils.alinear_a_schema_ra ────────────────────────────────────────

class TestAlinearASchemaRa:
    """Pruebas directas del helper de alineación (también usado por consolidar_ra)."""

    def test_agrega_columnas_faltantes(self):
        from emces.utils import alinear_a_schema_ra
        df = pd.DataFrame({"flujo_comercial": ["X"], "periodo": ["2026"]})
        resultado = alinear_a_schema_ra(df, "test")
        assert list(resultado.columns) == ORDEN_FINAL_RA
        # columna que no estaba en df original debe ser ""
        assert resultado["idnoremp"].iloc[0] == ""

    def test_descarta_columnas_extra(self):
        from emces.utils import alinear_a_schema_ra
        df = pd.DataFrame({col: ["x"] for col in ORDEN_FINAL_RA})
        df["columna_basura"] = "Y"
        resultado = alinear_a_schema_ra(df, "test")
        assert "columna_basura" not in resultado.columns

    def test_orden_columnas_exacto(self):
        from emces.utils import alinear_a_schema_ra
        df = pd.DataFrame({col: ["x"] for col in reversed(ORDEN_FINAL_RA)})
        resultado = alinear_a_schema_ra(df, "test")
        assert list(resultado.columns) == ORDEN_FINAL_RA
