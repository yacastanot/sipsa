"""Tests unitarios — FASE 4: Pipeline de Agregación."""
from __future__ import annotations

import pandas as pd
import pytest

from sipsa_abastecimiento.pipelines.aggregation.nodes import (
    calcular_td_abast,
    calcular_td_abast_otros,
    calcular_td_destino,
    calcular_td_total,
)

# ─── fixture base ─────────────────────────────────────────────────────────────

def _ipc2() -> pd.DataFrame:
    """Base IPC2 mínima con 3 artículos, 3 períodos y datos de importación."""
    filas = [
        # Mes actual — ARROZ (1001) — Colombia
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "PerFecha": "Mes actual",
         "Cant_Ton": 100.0, "Ciudad": "Bogotá, D.C.", "Departamento Proc.": "CUNDINAMARCA", "Municipio Proc.": "FUSAGASUGÁ"},
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "PerFecha": "Mes actual",
         "Cant_Ton": 50.0, "Ciudad": "Cali", "Departamento Proc.": "VALLE DEL CAUCA", "Municipio Proc.": "JAMUNDÍ"},
        # Mes actual — PAPA (1019)
        {"RArtículo_IPC": 1019, "Artículo_IPC": "PAPA", "PerFecha": "Mes actual",
         "Cant_Ton": 200.0, "Ciudad": "Bogotá, D.C.", "Departamento Proc.": "BOYACÁ", "Municipio Proc.": "TUNJA"},
        # Mes actual — importación (Depto=OTRO)
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "PerFecha": "Mes actual",
         "Cant_Ton": 30.0, "Ciudad": "Bogotá, D.C.", "Departamento Proc.": "n.a.", "Municipio Proc.": "ESTADOS UNIDOS DE AMERICA"},
        # Mes anterior
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "PerFecha": "Mes anterior",
         "Cant_Ton": 120.0, "Ciudad": "Bogotá, D.C.", "Departamento Proc.": "CUNDINAMARCA", "Municipio Proc.": "FUSAGASUGÁ"},
        # Año anterior
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "PerFecha": "Año anterior",
         "Cant_Ton": 90.0, "Ciudad": "Bogotá, D.C.", "Departamento Proc.": "CUNDINAMARCA", "Municipio Proc.": "FUSAGASUGÁ"},
        # Mes anterior — PAPA
        {"RArtículo_IPC": 1019, "Artículo_IPC": "PAPA", "PerFecha": "Mes anterior",
         "Cant_Ton": 180.0, "Ciudad": "Bogotá, D.C.", "Departamento Proc.": "BOYACÁ", "Municipio Proc.": "TUNJA"},
        # Año anterior — PAPA
        {"RArtículo_IPC": 1019, "Artículo_IPC": "PAPA", "PerFecha": "Año anterior",
         "Cant_Ton": 210.0, "Ciudad": "Bogotá, D.C.", "Departamento Proc.": "BOYACÁ", "Municipio Proc.": "TUNJA"},
    ]
    df = pd.DataFrame(filas)
    df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
    return df


# ─── TD_Total ─────────────────────────────────────────────────────────────────

class TestCalcularTdTotal:
    def test_columnas_requeridas(self):
        resultado = calcular_td_total(_ipc2())
        assert {"RArtículo_IPC", "Artículo_IPC",
                "AbastTotal_MesActual", "AbastTotal_MesAnterior",
                "AbastTotal_AnoAnterior"}.issubset(resultado.columns)

    def test_suma_mes_actual_arroz(self):
        resultado = calcular_td_total(_ipc2())
        arroz = resultado.loc[resultado["RArtículo_IPC"].eq(1001)]
        # 100 + 50 + 30 (importacion cuenta como mes actual)
        assert arroz["AbastTotal_MesActual"].iloc[0] == pytest.approx(180.0)

    def test_suma_mes_anterior_arroz(self):
        resultado = calcular_td_total(_ipc2())
        arroz = resultado.loc[resultado["RArtículo_IPC"].eq(1001)]
        assert arroz["AbastTotal_MesAnterior"].iloc[0] == pytest.approx(120.0)

    def test_suma_anio_anterior_arroz(self):
        resultado = calcular_td_total(_ipc2())
        arroz = resultado.loc[resultado["RArtículo_IPC"].eq(1001)]
        assert arroz["AbastTotal_AnoAnterior"].iloc[0] == pytest.approx(90.0)

    def test_suma_mes_actual_papa(self):
        resultado = calcular_td_total(_ipc2())
        papa = resultado.loc[resultado["RArtículo_IPC"].eq(1019)]
        assert papa["AbastTotal_MesActual"].iloc[0] == pytest.approx(200.0)

    def test_articulos_en_resultado(self):
        resultado = calcular_td_total(_ipc2())
        assert set(resultado["RArtículo_IPC"].tolist()) == {1001, 1019}

    def test_ordenado_por_rarticulo(self):
        resultado = calcular_td_total(_ipc2())
        codigos = resultado["RArtículo_IPC"].tolist()
        assert codigos == sorted(codigos)

    def test_base_vacia(self):
        df = pd.DataFrame(columns=["RArtículo_IPC", "Artículo_IPC", "PerFecha", "Cant_Ton",
                                   "Ciudad", "Departamento Proc.", "Municipio Proc."])
        df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
        resultado = calcular_td_total(df)
        assert resultado.empty or resultado["AbastTotal_MesActual"].sum() == 0


# ─── TD_Abast ─────────────────────────────────────────────────────────────────

class TestCalcularTdAbast:
    def test_columnas_requeridas(self):
        resultado = calcular_td_abast(_ipc2())
        assert {"RArtículo_IPC", "Artículo_IPC", "Departamento Proc.",
                "Sum_Ton", "Total_Artículo", "Participación"}.issubset(resultado.columns)

    def test_participacion_suma_100_por_articulo(self):
        resultado = calcular_td_abast(_ipc2())
        for cod, grupo in resultado.groupby("RArtículo_IPC"):
            # Tolerancia 0.1: redondear cada fila individualmente puede sumar 100.01
            assert grupo["Participación"].sum() == pytest.approx(100.0, abs=0.1)

    def test_participacion_redondeada_2_decimales(self):
        resultado = calcular_td_abast(_ipc2())
        for val in resultado["Participación"]:
            assert round(val, 2) == val

    def test_solo_mes_actual(self):
        # La suma total de TD_Abast debe ser solo del mes actual
        df = _ipc2()
        resultado = calcular_td_abast(df)
        suma_mes_actual = df.loc[df["PerFecha"].eq("Mes actual"), "Cant_Ton"].sum()
        assert resultado["Sum_Ton"].sum() == pytest.approx(suma_mes_actual)

    def test_cundinamarca_arroz_participacion(self):
        resultado = calcular_td_abast(_ipc2())
        arroz_cundi = resultado.loc[
            resultado["RArtículo_IPC"].eq(1001)
            & resultado["Departamento Proc."].eq("CUNDINAMARCA")
        ]
        # ARROZ mes actual: 100 (Cundi) + 50 (Valle) + 30 (OTRO) = 180 total
        # Cundi: 100/180*100 = 55.56%
        assert arroz_cundi["Participación"].iloc[0] == pytest.approx(55.56, abs=0.01)


# ─── TD_Destino ───────────────────────────────────────────────────────────────

class TestCalcularTdDestino:
    def test_columnas_requeridas(self):
        resultado = calcular_td_destino(_ipc2())
        assert {"RArtículo_IPC", "Artículo_IPC", "Ciudad",
                "Sum_Ton", "Total_Artículo", "Participación"}.issubset(resultado.columns)

    def test_participacion_suma_100_por_articulo(self):
        resultado = calcular_td_destino(_ipc2())
        for cod, grupo in resultado.groupby("RArtículo_IPC"):
            assert grupo["Participación"].sum() == pytest.approx(100.0, abs=0.01)

    def test_solo_mes_actual(self):
        df = _ipc2()
        resultado = calcular_td_destino(df)
        suma_mes_actual = df.loc[df["PerFecha"].eq("Mes actual"), "Cant_Ton"].sum()
        assert resultado["Sum_Ton"].sum() == pytest.approx(suma_mes_actual)

    def test_ciudades_presentes(self):
        resultado = calcular_td_destino(_ipc2())
        assert "Bogotá, D.C." in resultado["Ciudad"].values
        assert "Cali" in resultado["Ciudad"].values


# ─── TD_Abast_Otros ───────────────────────────────────────────────────────────

class TestCalcularTdAbastOtros:
    def test_columnas_requeridas(self):
        resultado = calcular_td_abast_otros(_ipc2())
        assert {"RArtículo_IPC", "Artículo_IPC", "Municipio Proc.",
                "Sum_Ton", "Total_Artículo", "Participación"}.issubset(resultado.columns)

    def test_solo_registros_otro(self):
        resultado = calcular_td_abast_otros(_ipc2())
        # Solo ARROZ tiene importaciones en el fixture
        assert set(resultado["RArtículo_IPC"].tolist()) == {1001}

    def test_participacion_100(self):
        resultado = calcular_td_abast_otros(_ipc2())
        # Solo hay un país de importación → Participación debe ser 100%
        assert resultado["Participación"].iloc[0] == pytest.approx(100.0)

    def test_sin_importaciones_devuelve_vacio(self):
        df = _ipc2()
        df_sin_otros = df.loc[df["Departamento Proc."].ne("n.a.")].copy()
        resultado = calcular_td_abast_otros(df_sin_otros)
        assert resultado.empty

    def test_suma_correcta_importacion(self):
        resultado = calcular_td_abast_otros(_ipc2())
        # Solo hay 30 ton de importación de ARROZ
        assert resultado["Sum_Ton"].sum() == pytest.approx(30.0)
