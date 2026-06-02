"""Pruebas unitarias del patrón Strategy para fuentes RA.

Cubre:
  SourceStrategy            métodos de clase (verificar_compatibilidad,
                             verificar_duplicados_periodo)
  HistoricalRAStrategy      read(), validate_schema(), prepare() end-to-end
  FletesStrategy            validate_schema(), prepare() end-to-end
  CancilleriaStrategy       validate_schema(), prepare() end-to-end
  Extensibilidad            agregar nueva estrategia sin tocar el registro
"""
from __future__ import annotations

import warnings

import pandas as pd
import pytest

from emces.utils import ORDEN_FINAL_RA, alinear_a_schema_ra
from emces.strategies.source_strategy import (
    COLS_MINIMAS_HISTORICO,
    SOURCE_REGISTRY,
    CancilleriaStrategy,
    FletesStrategy,
    HistoricalRAStrategy,
    SourceStrategy,
)


# ─── Fixtures compartidas ─────────────────────────────────────────────────────

def _df_minimo(periodo_mes: str = "2026_01", flujo: str = "IMPORTACIONES", n: int = 3) -> pd.DataFrame:
    """DataFrame con columnas mínimas de una fuente RA nueva."""
    return pd.DataFrame({
        "flujo_comercial": [flujo] * n,
        "periodo": ["2026"] * n,
        "mes": ["01"] * n,
        "periodo_mes": [periodo_mes] * n,
        "pais": ["170"] * n,
        "total_en_dolares": [100.0, 200.0, 300.0][:n],
        "total_en_miles_de_pesos": [400_000.0, 800_000.0, 1_200_000.0][:n],
    })


def _df_historico(periodos: list[str] | None = None, n_por_periodo: int = 2) -> pd.DataFrame:
    """Histórico simulado con varios periodos."""
    if periodos is None:
        periodos = ["2025_10", "2025_11", "2025_12"]
    partes = []
    for pm in periodos:
        partes.append(_df_minimo(periodo_mes=pm, n=n_por_periodo))
    return pd.concat(partes, ignore_index=True)


def _df_schema_ra(periodo_mes: str = "2026_01", n: int = 2) -> pd.DataFrame:
    """DataFrame completo alineado al schema ORDEN_FINAL_RA."""
    base = pd.DataFrame({col: [""] * n for col in ORDEN_FINAL_RA})
    base["periodo_mes"] = periodo_mes
    base["flujo_comercial"] = "IMPORTACIONES FLETES"
    base["periodo"] = "2026"
    base["mes"] = "01"
    base["total_en_dolares"] = [100.0, 200.0][:n]
    base["total_en_miles_de_pesos"] = [400_000.0, 800_000.0][:n]
    return base


# ─── SourceStrategy: métodos estáticos ────────────────────────────────────────

class TestVerificarCompatibilidad:
    def test_no_emite_warning_con_mismas_columnas(self):
        df_a = pd.DataFrame({"a": [1], "b": [2]})
        df_b = pd.DataFrame({"a": [3], "b": [4]})
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            SourceStrategy.verificar_compatibilidad([df_a, df_b], ["fuente_a", "fuente_b"])

    def test_emite_warning_cuando_una_tiene_columna_extra(self):
        df_a = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
        df_b = pd.DataFrame({"a": [4], "b": [5]})
        with pytest.warns(UserWarning, match="fuente_b.*c"):
            SourceStrategy.verificar_compatibilidad([df_a, df_b], ["fuente_a", "fuente_b"])

    def test_silencioso_con_lista_vacia(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            SourceStrategy.verificar_compatibilidad([], [])

    def test_silencioso_con_una_sola_fuente(self):
        df = pd.DataFrame({"a": [1]})
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            SourceStrategy.verificar_compatibilidad([df], ["sola"])


class TestVerificarDuplicadosPeriodo:
    def test_no_emite_warning_sin_solapamiento(self):
        historico = _df_historico(["2025_10", "2025_11"])
        nueva = _df_minimo("2026_01")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            SourceStrategy.verificar_duplicados_periodo(historico, nueva, "fletes")

    def test_emite_warning_con_solapamiento(self):
        historico = _df_historico(["2025_12", "2026_01"])
        nueva = _df_minimo("2026_01")  # periodo ya en histórico
        with pytest.warns(UserWarning, match="2026_01"):
            SourceStrategy.verificar_duplicados_periodo(historico, nueva, "fletes")

    def test_silencioso_sin_columna_periodo_mes(self):
        historico = pd.DataFrame({"otra_col": [1, 2]})
        nueva = pd.DataFrame({"otra_col": [3, 4]})
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            SourceStrategy.verificar_duplicados_periodo(historico, nueva, "fuente")


# ─── HistoricalRAStrategy ─────────────────────────────────────────────────────

class TestHistoricalRAStrategy:
    @pytest.fixture
    def strategy(self) -> HistoricalRAStrategy:
        return HistoricalRAStrategy()

    @pytest.fixture
    def df_historico_mayusculas(self) -> pd.DataFrame:
        """Simula Excel exportado desde SAS con columnas en MAYÚSCULAS."""
        df = _df_historico()
        df.columns = [c.upper() for c in df.columns]
        return df

    def test_get_source_name(self, strategy):
        assert strategy.get_source_name() == "historico"

    # ── read() ────────────────────────────────────────────────────────────────

    def test_read_normaliza_mayusculas_a_minusculas(self, strategy, df_historico_mayusculas):
        resultado = strategy.read(df_historico_mayusculas)
        assert all(c == c.lower() for c in resultado.columns)

    def test_read_elimina_espacios_en_nombres_de_columna(self, strategy):
        df = pd.DataFrame({"  FLUJO_COMERCIAL  ": [1], " PERIODO_MES ": [2]})
        resultado = strategy.read(df)
        assert "flujo_comercial" in resultado.columns
        assert "periodo_mes" in resultado.columns

    def test_read_no_modifica_datos(self, strategy):
        df = _df_historico()
        resultado = strategy.read(df)
        assert len(resultado) == len(df)
        assert resultado["periodo_mes"].tolist() == df["periodo_mes"].tolist()

    # ── validate_schema() ────────────────────────────────────────────────────

    def test_validate_ok_con_columnas_minimas(self, strategy):
        df = _df_historico()
        strategy.validate_schema(df)  # no debe lanzar

    def test_validate_lanza_error_si_historico_vacio(self, strategy):
        df_vacio = pd.DataFrame(columns=COLS_MINIMAS_HISTORICO)
        with pytest.raises(ValueError, match="vacío"):
            strategy.validate_schema(df_vacio)

    def test_validate_lanza_error_si_faltan_columnas(self, strategy):
        df = _df_historico().drop(columns=["total_en_dolares"])
        with pytest.raises(ValueError, match="total_en_dolares"):
            strategy.validate_schema(df)

    @pytest.mark.parametrize("col_faltante", COLS_MINIMAS_HISTORICO)
    def test_validate_detecta_cada_columna_faltante(self, strategy, col_faltante):
        df = _df_historico()
        df_sin_col = df.drop(columns=[col_faltante])
        with pytest.raises(ValueError):
            strategy.validate_schema(df_sin_col)

    # ── prepare() end-to-end ──────────────────────────────────────────────────

    def test_prepare_retorna_schema_canonico(self, strategy):
        df = _df_historico()
        resultado = strategy.prepare(df)
        assert list(resultado.columns) == ORDEN_FINAL_RA

    def test_prepare_acepta_columnas_en_mayusculas(self, strategy, df_historico_mayusculas):
        resultado = strategy.prepare(df_historico_mayusculas)
        assert list(resultado.columns) == ORDEN_FINAL_RA
        assert len(resultado) == len(df_historico_mayusculas)

    def test_prepare_conserva_numero_de_filas(self, strategy):
        df = _df_historico(periodos=["2025_11", "2025_12"])
        resultado = strategy.prepare(df)
        assert len(resultado) == len(df)

    def test_prepare_lanza_error_con_historico_vacio(self, strategy):
        df_vacio = pd.DataFrame(columns=list(_df_historico().columns))
        with pytest.raises(ValueError, match="vacío"):
            strategy.prepare(df_vacio)

    def test_prepare_columnas_monetarias_son_float64(self, strategy):
        df = _df_historico()
        resultado = strategy.prepare(df)
        assert pd.api.types.is_float_dtype(resultado["total_en_dolares"])
        assert pd.api.types.is_float_dtype(resultado["total_en_miles_de_pesos"])


# ─── FletesStrategy ───────────────────────────────────────────────────────────

class TestFletesStrategy:
    @pytest.fixture
    def strategy(self) -> FletesStrategy:
        return FletesStrategy()

    @pytest.fixture
    def fletes_maestro(self) -> pd.DataFrame:
        """fletes_maestro simulado (salida del pipeline fletes)."""
        return _df_schema_ra("2026_01")

    def test_get_source_name(self, strategy):
        assert strategy.get_source_name() == "fletes"

    def test_read_es_identidad(self, strategy, fletes_maestro):
        resultado = strategy.read(fletes_maestro)
        pd.testing.assert_frame_equal(resultado, fletes_maestro)

    # ── validate_schema() ────────────────────────────────────────────────────

    def test_validate_ok_con_periodo_mes(self, strategy, fletes_maestro):
        strategy.validate_schema(fletes_maestro)  # no debe lanzar

    def test_validate_lanza_error_si_vacio(self, strategy):
        df_vacio = pd.DataFrame(columns=list(_df_schema_ra().columns))
        with pytest.raises(ValueError, match="vacío"):
            strategy.validate_schema(df_vacio)

    def test_validate_lanza_error_sin_periodo_mes(self, strategy):
        df = _df_schema_ra().drop(columns=["periodo_mes"])
        with pytest.raises(ValueError, match="periodo_mes"):
            strategy.validate_schema(df)

    def test_validate_emite_warning_con_multiples_periodos(self, strategy, caplog):
        df = pd.concat([
            _df_schema_ra("2026_01"),
            _df_schema_ra("2026_02"),
        ], ignore_index=True)
        import logging
        with caplog.at_level(logging.WARNING, logger="emces.strategies.source_strategy"):
            strategy.validate_schema(df)
        assert any("2" in r.message for r in caplog.records if r.levelno == logging.WARNING)

    # ── prepare() end-to-end ──────────────────────────────────────────────────

    def test_prepare_retorna_schema_canonico(self, strategy, fletes_maestro):
        resultado = strategy.prepare(fletes_maestro)
        assert list(resultado.columns) == ORDEN_FINAL_RA

    def test_prepare_conserva_filas(self, strategy, fletes_maestro):
        resultado = strategy.prepare(fletes_maestro)
        assert len(resultado) == len(fletes_maestro)

    def test_prepare_columnas_monetarias_son_float64(self, strategy, fletes_maestro):
        resultado = strategy.prepare(fletes_maestro)
        assert pd.api.types.is_float_dtype(resultado["total_en_dolares"])

    def test_prepare_descarta_columnas_extras(self, strategy, fletes_maestro):
        df_con_extra = fletes_maestro.copy()
        df_con_extra["columna_extra_interna"] = "valor"
        resultado = strategy.prepare(df_con_extra)
        assert "columna_extra_interna" not in resultado.columns
        assert list(resultado.columns) == ORDEN_FINAL_RA


# ─── CancilleriaStrategy ──────────────────────────────────────────────────────

class TestCancilleriaStrategy:
    @pytest.fixture
    def strategy(self) -> CancilleriaStrategy:
        return CancilleriaStrategy()

    @pytest.fixture
    def canc_maestro(self) -> pd.DataFrame:
        """canc_maestro simulado (salida del pipeline cancilleria)."""
        return _df_schema_ra("2026_01")

    def test_get_source_name(self, strategy):
        assert strategy.get_source_name() == "cancilleria"

    def test_read_es_identidad(self, strategy, canc_maestro):
        resultado = strategy.read(canc_maestro)
        pd.testing.assert_frame_equal(resultado, canc_maestro)

    # ── validate_schema() ────────────────────────────────────────────────────

    def test_validate_ok_con_datos_validos(self, strategy, canc_maestro):
        strategy.validate_schema(canc_maestro)  # no debe lanzar

    def test_validate_lanza_error_si_vacio(self, strategy):
        df_vacio = pd.DataFrame(columns=list(_df_schema_ra().columns))
        with pytest.raises(ValueError, match="vacío"):
            strategy.validate_schema(df_vacio)

    def test_validate_lanza_error_sin_periodo_mes(self, strategy):
        df = _df_schema_ra().drop(columns=["periodo_mes"])
        with pytest.raises(ValueError, match="periodo_mes"):
            strategy.validate_schema(df)

    # ── prepare() end-to-end ──────────────────────────────────────────────────

    def test_prepare_retorna_schema_canonico(self, strategy, canc_maestro):
        resultado = strategy.prepare(canc_maestro)
        assert list(resultado.columns) == ORDEN_FINAL_RA

    def test_prepare_conserva_filas(self, strategy, canc_maestro):
        resultado = strategy.prepare(canc_maestro)
        assert len(resultado) == len(canc_maestro)

    def test_prepare_columnas_monetarias_son_float64(self, strategy, canc_maestro):
        resultado = strategy.prepare(canc_maestro)
        assert pd.api.types.is_float_dtype(resultado["total_en_dolares"])


# ─── SOURCE_REGISTRY ─────────────────────────────────────────────────────────

class TestSourceRegistry:
    def test_registro_contiene_fuentes_base(self):
        assert "historico" in SOURCE_REGISTRY
        assert "fletes" in SOURCE_REGISTRY
        assert "cancilleria" in SOURCE_REGISTRY

    def test_todas_las_estrategias_son_source_strategy(self):
        for nombre, estrategia in SOURCE_REGISTRY.items():
            assert isinstance(estrategia, SourceStrategy), (
                f"'{nombre}' no es instancia de SourceStrategy"
            )

    def test_nombres_coherentes_con_get_source_name(self):
        for nombre, estrategia in SOURCE_REGISTRY.items():
            assert estrategia.get_source_name() == nombre, (
                f"Clave del registro '{nombre}' ≠ get_source_name() '{estrategia.get_source_name()}'"
            )


# ─── Extensibilidad: nueva estrategia ────────────────────────────────────────

class TestExtensibilidadConNuevaEstrategia:
    """Demuestra que agregar una nueva fuente (ej. Viajes) no requiere
    modificar el código existente, solo crear una nueva subclase."""

    def _crear_viajes_strategy(self) -> SourceStrategy:
        """Estrategia de ejemplo para el pipeline Viajes (pendiente en diagrama)."""
        from emces.utils import alinear_a_schema_ra, validar_columnas

        class ViajesStrategy(SourceStrategy):
            def get_source_name(self) -> str:
                return "viajes"

            def validate_schema(self, df: pd.DataFrame) -> None:
                validar_columnas(df, ["periodo_mes", "flujo_comercial"], "ViajesStrategy")
                if df.empty:
                    raise ValueError("[ViajesStrategy] viajes_maestro está vacío.")

            def transform(self, df: pd.DataFrame) -> pd.DataFrame:
                return alinear_a_schema_ra(df, fuente="viajes")

        return ViajesStrategy()

    def test_nueva_estrategia_implementa_interfaz(self):
        estrategia = self._crear_viajes_strategy()
        assert isinstance(estrategia, SourceStrategy)
        assert estrategia.get_source_name() == "viajes"

    def test_nueva_estrategia_prepare_funciona(self):
        estrategia = self._crear_viajes_strategy()
        df = _df_schema_ra("2026_01")
        resultado = estrategia.prepare(df)
        assert list(resultado.columns) == ORDEN_FINAL_RA

    def test_nueva_estrategia_registrable_en_registry(self):
        estrategia = self._crear_viajes_strategy()
        registro_extendido = {**SOURCE_REGISTRY, "viajes": estrategia}
        assert "viajes" in registro_extendido
        assert registro_extendido["viajes"].get_source_name() == "viajes"

    def test_clase_abstracta_no_instanciable_directamente(self):
        with pytest.raises(TypeError):
            SourceStrategy()  # type: ignore[abstract]
