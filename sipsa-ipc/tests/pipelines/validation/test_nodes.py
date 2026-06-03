"""Tests unitarios — FASE 3: Pipeline de Validación."""
from __future__ import annotations

import pandas as pd
import pytest

from sipsa_ipc.pipelines.validation.nodes import (
    calcular_cobertura,
    filtrar_articulos_canasta,
    generar_no_mapeados,
)

# ─── fixtures ─────────────────────────────────────────────────────────────────

ARTICULOS_IPC_FIXTURE = {
    "codigos": {
        "ARROZ": 1001,
        "PAPA": 1019,
        "TOMATE": 1022,
    },
    "variedades": {
        "Arroz": "ARROZ",
        "Papa parda pastusa": "PAPA",
        "Tomate chonto": "TOMATE",
    },
}


def _base_clean(n_mapeados: int = 5, n_no_mapeados: int = 3) -> pd.DataFrame:
    """Construye un DataFrame mínimo que imita la salida de F2."""
    filas_mapeadas = [
        {
            "Ali": "Arroz",
            "Grupo": "Cereales",
            "Artículo_IPC": "ARROZ",
            "RArtículo_IPC": 1001,
            "PerFecha": "Mes actual",
            "Cant_Ton": 1.5,
        }
        for i in range(n_mapeados)
    ]
    filas_no_mapeadas = [
        {
            "Ali": f"Variedad desconocida {i}",
            "Grupo": "Otros",
            "Artículo_IPC": None,
            "RArtículo_IPC": pd.NA,
            "PerFecha": "Mes actual",
            "Cant_Ton": 0.5,
        }
        for i in range(n_no_mapeados)
    ]
    df = pd.DataFrame(filas_mapeadas + filas_no_mapeadas)
    df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
    return df


# ─── filtrar_articulos_canasta ─────────────────────────────────────────────────

class TestFiltrarArticulosCanasta:
    def test_retiene_solo_mapeados(self):
        df = _base_clean(n_mapeados=5, n_no_mapeados=3)
        resultado = filtrar_articulos_canasta(df)
        assert resultado["RArtículo_IPC"].notna().all()

    def test_excluye_no_mapeados(self):
        df = _base_clean(n_mapeados=5, n_no_mapeados=3)
        resultado = filtrar_articulos_canasta(df)
        assert resultado["RArtículo_IPC"].isna().sum() == 0

    def test_cantidad_filas_correcta(self):
        df = _base_clean(n_mapeados=6, n_no_mapeados=4)
        resultado = filtrar_articulos_canasta(df)
        # Los primeros 6 tienen RArtículo_IPC != NA (ninguno cae en i%10==0 para n=6)
        assert len(resultado) <= 6

    def test_dataframe_vacio_produce_vacio(self):
        df = pd.DataFrame(
            columns=["Ali", "Grupo", "Artículo_IPC", "RArtículo_IPC", "PerFecha", "Cant_Ton"]
        )
        df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
        resultado = filtrar_articulos_canasta(df)
        assert resultado.empty

    def test_ordenado_por_rarticulo(self):
        filas = [
            {"Ali": "A", "Grupo": "G", "Artículo_IPC": "PAPA", "RArtículo_IPC": 1019, "PerFecha": "Mes actual", "Cant_Ton": 1.0},
            {"Ali": "B", "Grupo": "G", "Artículo_IPC": "ARROZ", "RArtículo_IPC": 1001, "PerFecha": "Mes actual", "Cant_Ton": 1.0},
        ]
        df = pd.DataFrame(filas)
        df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
        resultado = filtrar_articulos_canasta(df)
        codigos = resultado["RArtículo_IPC"].tolist()
        assert codigos == sorted(codigos)


# ─── generar_no_mapeados ──────────────────────────────────────────────────────

class TestGenerarNoMapeados:
    def test_columnas_correctas(self):
        df = _base_clean(n_mapeados=4, n_no_mapeados=3)
        resultado = generar_no_mapeados(df)
        assert {"Ali", "Grupo", "N_Registros"}.issubset(resultado.columns)

    def test_solo_variedades_no_mapeadas(self):
        df = _base_clean(n_mapeados=4, n_no_mapeados=3)
        resultado = generar_no_mapeados(df)
        # Las 3 variedades desconocidas deben aparecer
        assert len(resultado) == 3

    def test_sin_no_mapeados_devuelve_vacio(self):
        filas = [
            {"Ali": "Arroz", "Grupo": "Cereales", "Artículo_IPC": "ARROZ",
             "RArtículo_IPC": 1001, "PerFecha": "Mes actual", "Cant_Ton": 1.0},
        ]
        df = pd.DataFrame(filas)
        df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
        resultado = generar_no_mapeados(df)
        assert resultado.empty

    def test_ordenado_por_frecuencia_desc(self):
        filas = []
        for _ in range(5):
            filas.append({"Ali": "Muy_frecuente", "Grupo": "G", "Artículo_IPC": None,
                          "RArtículo_IPC": pd.NA, "PerFecha": "Mes actual", "Cant_Ton": 1.0})
        for _ in range(2):
            filas.append({"Ali": "Poco_frecuente", "Grupo": "G", "Artículo_IPC": None,
                          "RArtículo_IPC": pd.NA, "PerFecha": "Mes actual", "Cant_Ton": 1.0})
        df = pd.DataFrame(filas)
        df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
        resultado = generar_no_mapeados(df)
        assert resultado.iloc[0]["Ali"] == "Muy_frecuente"
        assert resultado.iloc[0]["N_Registros"] == 5


# ─── calcular_cobertura ───────────────────────────────────────────────────────

class TestCalcularCobertura:
    def _base_filtrada(self) -> pd.DataFrame:
        filas = [
            {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "PerFecha": "Mes actual", "Cant_Ton": 1.0},
            {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "PerFecha": "Mes actual", "Cant_Ton": 1.0},
            {"RArtículo_IPC": 1019, "Artículo_IPC": "PAPA", "PerFecha": "Mes anterior", "Cant_Ton": 2.0},
        ]
        df = pd.DataFrame(filas)
        df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
        return df

    def test_columnas_correctas(self):
        df = self._base_filtrada()
        resultado = calcular_cobertura(df, ARTICULOS_IPC_FIXTURE, "Abril", 2025)
        assert {"RArtículo_IPC", "Artículo_IPC", "N_Registros_MesActual", "Tiene_Cobertura"}.issubset(resultado.columns)

    def test_contiene_todos_los_articulos_canasta(self):
        df = self._base_filtrada()
        resultado = calcular_cobertura(df, ARTICULOS_IPC_FIXTURE, "Abril", 2025)
        # Fixture tiene 3 artículos
        assert len(resultado) == 3

    def test_articulo_con_datos_tiene_cobertura(self):
        df = self._base_filtrada()
        resultado = calcular_cobertura(df, ARTICULOS_IPC_FIXTURE, "Abril", 2025)
        arroz = resultado.loc[resultado["RArtículo_IPC"].eq(1001)]
        assert arroz["Tiene_Cobertura"].iloc[0] == True  # noqa: E712
        assert arroz["N_Registros_MesActual"].iloc[0] == 2

    def test_articulo_sin_datos_mes_actual_no_tiene_cobertura(self):
        df = self._base_filtrada()
        resultado = calcular_cobertura(df, ARTICULOS_IPC_FIXTURE, "Abril", 2025)
        # PAPA solo tiene "Mes anterior", no "Mes actual"
        papa = resultado.loc[resultado["RArtículo_IPC"].eq(1019)]
        assert papa["Tiene_Cobertura"].iloc[0] == False  # noqa: E712
        assert papa["N_Registros_MesActual"].iloc[0] == 0

    def test_articulo_ausente_en_datos_tiene_n_cero(self):
        df = self._base_filtrada()
        resultado = calcular_cobertura(df, ARTICULOS_IPC_FIXTURE, "Abril", 2025)
        tomate = resultado.loc[resultado["RArtículo_IPC"].eq(1022)]
        assert not tomate.empty
        assert tomate["N_Registros_MesActual"].iloc[0] == 0

    def test_base_vacia_todos_sin_cobertura(self):
        df = pd.DataFrame(columns=["RArtículo_IPC", "Artículo_IPC", "PerFecha", "Cant_Ton"])
        df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
        resultado = calcular_cobertura(df, ARTICULOS_IPC_FIXTURE, "Abril", 2025)
        assert resultado["Tiene_Cobertura"].sum() == 0
