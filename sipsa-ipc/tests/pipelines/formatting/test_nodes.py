"""Tests unitarios — FASE 6: Formato, Normalización y Ordenamiento."""
from __future__ import annotations

import pandas as pd
import pytest

from sipsa_abastecimiento.pipelines.formatting.nodes import (
    _CORRECCIONES_DEPTOS,
    _CORRECCIONES_PAISES,
    _propcase_es,
    formatear_td_abast,
    formatear_td_abast_otros,
    formatear_td_destino,
)

# ─── fixture helpers ──────────────────────────────────────────────────────────

def _td_abast() -> pd.DataFrame:
    """TD_Abast mínima en mayúsculas, sin ordenar."""
    filas = [
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "Departamento Proc.": "TOLIMA",
         "Sum_Ton": 5403.21, "Total_Artículo": 22451.17, "Participación": 24.07},
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "Departamento Proc.": "VALLE DEL CAUCA",
         "Sum_Ton": 71.53, "Total_Artículo": 22451.17, "Participación": 0.32},
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "Departamento Proc.": "NORTE DE SANTANDER",
         "Sum_Ton": 2838.90, "Total_Artículo": 22451.17, "Participación": 12.64},
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "Departamento Proc.": "META",
         "Sum_Ton": 5188.65, "Total_Artículo": 22451.17, "Participación": 23.11},
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "Departamento Proc.": "n.a.",
         "Sum_Ton": 463.50, "Total_Artículo": 22451.17, "Participación": 2.06},
        {"RArtículo_IPC": 1019, "Artículo_IPC": "PAPA", "Departamento Proc.": "BOYACÁ",
         "Sum_Ton": 50000.0, "Total_Artículo": 89608.84, "Participación": 55.80},
        {"RArtículo_IPC": 1019, "Artículo_IPC": "PAPA", "Departamento Proc.": "CUNDINAMARCA",
         "Sum_Ton": 30000.0, "Total_Artículo": 89608.84, "Participación": 33.48},
    ]
    df = pd.DataFrame(filas)
    df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
    return df


def _td_destino() -> pd.DataFrame:
    filas = [
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "Ciudad": "Barranquilla",
         "Sum_Ton": 6620.33, "Total_Artículo": 22451.17, "Participación": 29.49},
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "Ciudad": "Bogotá, D.C.",
         "Sum_Ton": 4411.60, "Total_Artículo": 22451.17, "Participación": 19.65},
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "Ciudad": "Medellín",
         "Sum_Ton": 6264.10, "Total_Artículo": 22451.17, "Participación": 27.90},
    ]
    df = pd.DataFrame(filas)
    df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
    return df


def _td_abast_otros() -> pd.DataFrame:
    filas = [
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "Municipio Proc.": "ECUADOR",
         "Sum_Ton": 460.0, "Total_Artículo": 463.5, "Participación": 99.24},
        {"RArtículo_IPC": 1001, "Artículo_IPC": "ARROZ", "Municipio Proc.": "CANADÁ",
         "Sum_Ton": 3.5, "Total_Artículo": 463.5, "Participación": 0.76},
        {"RArtículo_IPC": 1003, "Artículo_IPC": "CARNE DE RES SIN HUESO",
         "Municipio Proc.": "ESTADOS UNIDOS DE AMÉRICA",
         "Sum_Ton": 54.0, "Total_Artículo": 54.0, "Participación": 100.0},
        {"RArtículo_IPC": 1004, "Artículo_IPC": "CARNE DE CERDO SIN HUESO",
         "Municipio Proc.": "ESTADOS UNIDOS DE AMÉRICA",
         "Sum_Ton": 1915.48, "Total_Artículo": 2000.98, "Participación": 95.73},
        {"RArtículo_IPC": 1004, "Artículo_IPC": "CARNE DE CERDO SIN HUESO",
         "Municipio Proc.": "BÉLGICA",
         "Sum_Ton": 24.0, "Total_Artículo": 2000.98, "Participación": 1.20},
    ]
    df = pd.DataFrame(filas)
    df["RArtículo_IPC"] = df["RArtículo_IPC"].astype("Int64")
    return df


# ─── _propcase_es ─────────────────────────────────────────────────────────────

class TestPropcaseEs:
    def test_mayusculas_simples(self):
        assert _propcase_es("CUNDINAMARCA") == "Cundinamarca"

    def test_mayusculas_con_tilde(self):
        assert _propcase_es("BOYACÁ") == "Boyacá"

    def test_bogota_dc(self):
        # Verifica que la coma y el punto no rompan el PropCase
        assert _propcase_es("BOGOTÁ, D.C.") == "Bogotá, D.C."

    def test_na_puntado(self):
        # SAS propcase de "n.a." → "N.A."
        assert _propcase_es("n.a.") == "N.A."

    def test_valle_del_cauca_sin_correccion(self):
        # title() da "Valle Del Cauca" — la corrección se aplica aparte
        assert _propcase_es("VALLE DEL CAUCA") == "Valle Del Cauca"

    def test_norte_de_santander_sin_correccion(self):
        assert _propcase_es("NORTE DE SANTANDER") == "Norte De Santander"

    def test_pais_estados_unidos(self):
        assert _propcase_es("ESTADOS UNIDOS DE AMÉRICA") == "Estados Unidos De América"


# ─── correcciones ─────────────────────────────────────────────────────────────

class TestCorrecciones:
    def test_correcciones_deptos_tiene_valle(self):
        assert "Valle Del Cauca" in _CORRECCIONES_DEPTOS
        assert _CORRECCIONES_DEPTOS["Valle Del Cauca"] == "Valle del Cauca"

    def test_correcciones_deptos_tiene_norte(self):
        assert "Norte De Santander" in _CORRECCIONES_DEPTOS
        assert _CORRECCIONES_DEPTOS["Norte De Santander"] == "Norte de Santander"

    def test_correcciones_paises_tiene_eeuu(self):
        assert "Estados Unidos De América" in _CORRECCIONES_PAISES
        assert _CORRECCIONES_PAISES["Estados Unidos De América"] == "Estados Unidos de América"


# ─── formatear_td_abast ───────────────────────────────────────────────────────

class TestFormatearTdAbast:
    def test_columnas_preservadas(self):
        resultado = formatear_td_abast(_td_abast())
        assert {"RArtículo_IPC", "Artículo_IPC", "Departamento Proc.",
                "Sum_Ton", "Total_Artículo", "Participación"}.issubset(resultado.columns)

    def test_propcase_general(self):
        resultado = formatear_td_abast(_td_abast())
        deptos = resultado["Departamento Proc."].tolist()
        assert "TOLIMA" not in deptos
        assert "Tolima" in deptos

    def test_correccion_valle_del_cauca(self):
        resultado = formatear_td_abast(_td_abast())
        assert "Valle Del Cauca" not in resultado["Departamento Proc."].values
        assert "Valle del Cauca" in resultado["Departamento Proc."].values

    def test_correccion_norte_de_santander(self):
        resultado = formatear_td_abast(_td_abast())
        assert "Norte De Santander" not in resultado["Departamento Proc."].values
        assert "Norte de Santander" in resultado["Departamento Proc."].values

    def test_na_se_convierte_a_mayuscula(self):
        resultado = formatear_td_abast(_td_abast())
        assert "N.A." in resultado["Departamento Proc."].values

    def test_ordenado_por_rarticulo_asc(self):
        resultado = formatear_td_abast(_td_abast())
        codigos = resultado["RArtículo_IPC"].tolist()
        assert codigos == sorted(codigos)

    def test_ordenado_por_participacion_desc_dentro_de_articulo(self):
        resultado = formatear_td_abast(_td_abast())
        for cod, grupo in resultado.groupby("RArtículo_IPC", sort=False):
            partic = grupo["Participación"].tolist()
            assert partic == sorted(partic, reverse=True), (
                f"Artículo {cod} no está ordenado DESC: {partic}"
            )

    def test_filas_preservadas(self):
        fixture = _td_abast()
        resultado = formatear_td_abast(fixture)
        assert len(resultado) == len(fixture)

    def test_arroz_primer_depto_es_el_mayor(self):
        """La primera fila de ARROZ debe tener la mayor Participación."""
        resultado = formatear_td_abast(_td_abast())
        arroz = resultado.loc[resultado["RArtículo_IPC"].eq(1001)]
        assert arroz["Participación"].iloc[0] == arroz["Participación"].max()


# ─── formatear_td_destino ─────────────────────────────────────────────────────

class TestFormatearTdDestino:
    def test_ciudades_sin_cambio(self):
        """Ciudad no debe ser modificada — ya viene en PropCase desde F2."""
        fixture = _td_destino()
        resultado = formatear_td_destino(fixture)
        ciudades_orig = set(fixture["Ciudad"].tolist())
        ciudades_res = set(resultado["Ciudad"].tolist())
        assert ciudades_orig == ciudades_res

    def test_ordenado_desc_participacion(self):
        resultado = formatear_td_destino(_td_destino())
        arroz = resultado.loc[resultado["RArtículo_IPC"].eq(1001)]
        partic = arroz["Participación"].tolist()
        assert partic == sorted(partic, reverse=True)

    def test_primera_ciudad_arroz_es_mayor(self):
        resultado = formatear_td_destino(_td_destino())
        arroz = resultado.loc[resultado["RArtículo_IPC"].eq(1001)]
        assert arroz["Participación"].iloc[0] == arroz["Participación"].max()

    def test_filas_preservadas(self):
        fixture = _td_destino()
        assert len(formatear_td_destino(fixture)) == len(fixture)


# ─── formatear_td_abast_otros ─────────────────────────────────────────────────

class TestFormatearTdAbastOtros:
    def test_propcase_pais_simple(self):
        resultado = formatear_td_abast_otros(_td_abast_otros())
        paises = resultado["Municipio Proc."].tolist()
        assert "ECUADOR" not in paises
        assert "Ecuador" in paises

    def test_propcase_con_tilde(self):
        resultado = formatear_td_abast_otros(_td_abast_otros())
        assert "Canadá" in resultado["Municipio Proc."].values

    def test_correccion_estados_unidos(self):
        resultado = formatear_td_abast_otros(_td_abast_otros())
        assert "Estados Unidos De América" not in resultado["Municipio Proc."].values
        assert "Estados Unidos de América" in resultado["Municipio Proc."].values

    def test_belgica_con_acento(self):
        resultado = formatear_td_abast_otros(_td_abast_otros())
        assert "Bélgica" in resultado["Municipio Proc."].values

    def test_ordenado_desc_participacion_dentro_de_articulo(self):
        resultado = formatear_td_abast_otros(_td_abast_otros())
        for cod, grupo in resultado.groupby("RArtículo_IPC", sort=False):
            partic = grupo["Participación"].tolist()
            assert partic == sorted(partic, reverse=True)

    def test_tabla_vacia_devuelve_vacia(self):
        vacia = pd.DataFrame(columns=["RArtículo_IPC", "Artículo_IPC", "Municipio Proc.",
                                       "Sum_Ton", "Total_Artículo", "Participación"])
        vacia["RArtículo_IPC"] = vacia["RArtículo_IPC"].astype("Int64")
        resultado = formatear_td_abast_otros(vacia)
        assert resultado.empty

    def test_filas_preservadas(self):
        fixture = _td_abast_otros()
        assert len(formatear_td_abast_otros(fixture)) == len(fixture)

    def test_primer_pais_arroz_ecuador(self):
        """ARROZ tiene Ecuador con 99.24% → debe ser primero."""
        resultado = formatear_td_abast_otros(_td_abast_otros())
        arroz = resultado.loc[resultado["RArtículo_IPC"].eq(1001)]
        assert arroz.iloc[0]["Municipio Proc."] == "Ecuador"
