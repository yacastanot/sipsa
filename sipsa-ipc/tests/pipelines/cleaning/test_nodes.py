"""Tests unitarios — pipeline de limpieza SIPSA IPC (F2).

Cubre las tareas del cronograma:
  T11 — Estandarización texto (strip/compactar espacios)
  T12 — Parseo Fuente → Ciudad, Central
  T13 — Limpieza códigos DIVIPOLA (quitar comillas)
  T14 — Conversión Cant Kg → Cant_Ton
  T15 — Creación PerFecha según parámetros de período
  T16 — Mapeo Ali (variedad SIPSA) → Artículo_IPC + RArtículo_IPC
  T17 — Variedades no mapeadas → NaN (no explota)
  T18 — Validación numérica implícita vía asserts de regresión
"""
from __future__ import annotations

import pandas as pd
import pytest

from sipsa_abastecimiento.pipelines.cleaning.nodes import (
    _crear_ciudad_y_central,
    _crear_cantidad_toneladas,
    _limpiar_divipola,
    _normalizar_fechas,
    _mapear_articulos_ipc,
    limpiar_base,
)


# ─── Fixture y helpers ────────────────────────────────────────────────────────

ARTICULOS_IPC_TEST = {
    "codigos": {
        "ARROZ": 1001,
        "LIMÓN": 1002,
        "BANANO": 1009,
        "CEBOLLA CABEZONA": 1023,
    },
    "variedades": {
        "Arroz": "ARROZ",
        "Limón Tahití": "LIMÓN",
        "Banano Urabá": "BANANO",
        "Cebolla cabezona blanca": "CEBOLLA CABEZONA",
    },
}


def _base_bronze() -> pd.DataFrame:
    """DataFrame mínimo que replica la estructura real de BASE SIPSA_A."""
    return pd.DataFrame(
        {
            "Fuente": [
                "Bogotá, D.C., Corabastos",
                "Ipiales (Nariño), Centro de acopio",
                "Santa Marta (Magdalena), Mercado público",
                "Armenia, Mercar",
            ],
            "FechaEncuesta": pd.to_datetime(
                ["2025-04-01", "2025-03-15", "2024-04-20", "2025-04-10"]
            ),
            "HoraEncuesta": ["03:30:00", "04:00:00", "05:00:00", "06:00:00"],
            "TipoVehiculo": ["TP", "TP", "TP", "TP"],
            "PlacaVehiculo": ["AAA111", "BBB222", "CCC333", "DDD444"],
            "Cod. Depto Proc.": ["'11", " '52 ", "'47", "'63"],
            "Departamento Proc.": ["BOGOTÁ, D.C.", "NARIÑO", "MAGDALENA", "QUINDÍO"],
            "Cod. Municipio Proc.": ["'11001", "'52356", " '47001 ", "'63001"],
            "Municipio Proc.": ["BOGOTÁ, D.C.", "IPIALES", "SANTA MARTA", "ARMENIA"],
            "Observaciones": [None, "  texto   con espacios ", None, None],
            "Grupo": ["CEREALES"] * 4,
            "Codigo CPC": ["'0111101"] * 4,
            "Ali": [
                "Arroz",
                "Limón Tahití",
                "Banano Urabá",
                "Cebolla cabezona blanca",
            ],
            "Cant Pres": [1.0, 2.0, 3.0, 4.0],
            "Pres": ["BULTO"] * 4,
            "Peso Pres": [50.0, 50.0, 50.0, 50.0],
            "Cant Kg": [1000.0, 2500.0, 3000.0, 4500.0],
            "Digitador": [None, None, None, None],
        }
    )


# ─── T13: limpieza DIVIPOLA ───────────────────────────────────────────────────

def test_limpia_divipola_y_crea_cant_ton():
    result = limpiar_base(_base_bronze(), ARTICULOS_IPC_TEST, "Abril", "Marzo", 2025, 2024)
    assert result["Cod. Depto Proc."].tolist() == ["11", "52", "47", "63"]
    assert result["Cod. Municipio Proc."].tolist() == ["11001", "52356", "47001", "63001"]
    assert result["Cant_Ton"].tolist() == [1.0, 2.5, 3.0, 4.5]


def test_limpia_divipola_elimina_comilla_y_espacios():
    df = _base_bronze()
    _limpiar_divipola(df)
    assert df["Cod. Depto Proc."].tolist() == ["11", "52", "47", "63"]
    assert all(not str(v).startswith("'") for v in df["Cod. Depto Proc."])
    assert all(" " not in str(v) for v in df["Cod. Municipio Proc."])


# ─── T12: parseo Fuente → Ciudad / Central ────────────────────────────────────

def test_parsea_fuente_en_ciudad_y_central():
    result = limpiar_base(_base_bronze(), ARTICULOS_IPC_TEST, "Abril", "Marzo", 2025, 2024)
    assert result["Ciudad"].tolist() == [
        "Bogotá, D.C.",
        "Ipiales",
        "Santa Marta",
        "Armenia",
    ]
    assert result["Central"].tolist() == [
        "Corabastos",
        "Centro de acopio",
        "Mercado público",
        "Mercar",
    ]


def test_parsea_fuente_sin_coma():
    """Mercado sin coma: Central debe ser igual a Fuente completa."""
    df = _base_bronze()
    df["Fuente"] = ["Florencia (Caquetá)"] * 4
    _crear_ciudad_y_central(df)
    assert df["Ciudad"].tolist() == ["Florencia (Caquetá)"] * 4
    assert df["Central"].tolist() == ["Florencia (Caquetá)"] * 4


def test_parsea_fuente_tres_partes():
    """Fuente con 3 partes: Central = última parte."""
    df = _base_bronze()
    df["Fuente"] = ["Bogotá, D.C., Corabastos"] * 4
    _crear_ciudad_y_central(df)
    assert df["Ciudad"].tolist() == ["Bogotá, D.C."] * 4
    assert df["Central"].tolist() == ["Corabastos"] * 4


def test_parsea_fuente_dos_partes():
    """Fuente con 2 partes (ciudad, central): Ciudad y Central separados."""
    df = _base_bronze()
    df["Fuente"] = ["Cali, Cavasa"] * 4
    _crear_ciudad_y_central(df)
    assert df["Ciudad"].tolist() == ["Cali"] * 4
    assert df["Central"].tolist() == ["Cavasa"] * 4


# ─── T15: PerFecha según parámetros ──────────────────────────────────────────

def test_crea_perfecha_segun_parametros():
    result = limpiar_base(_base_bronze(), ARTICULOS_IPC_TEST, "Abril", "Marzo", 2025, 2024)
    assert result["PerFecha"].tolist() == [
        "Mes actual",
        "Mes anterior",
        "Año anterior",
        "Mes actual",
    ]


def test_perfecha_no_mapeado_es_nulo():
    """Fecha fuera de los tres períodos → PerFecha = NA."""
    df = _base_bronze()
    df["FechaEncuesta"] = pd.to_datetime(
        ["2023-01-01", "2023-01-01", "2023-01-01", "2023-01-01"]
    )
    result = limpiar_base(df, ARTICULOS_IPC_TEST, "Abril", "Marzo", 2025, 2024)
    assert result["PerFecha"].isna().all()


def test_perfecha_es_insensible_a_mayusculas_parametros():
    """El nombre del mes en parámetros es insensible a mayúsculas."""
    result = limpiar_base(_base_bronze(), ARTICULOS_IPC_TEST, "ABRIL", "MARZO", 2025, 2024)
    assert "Mes actual" in result["PerFecha"].values


def test_variables_ano_mes_mes2_creadas():
    """limpiar_base debe crear Año, Mes y Mes2."""
    result = limpiar_base(_base_bronze(), ARTICULOS_IPC_TEST, "Abril", "Marzo", 2025, 2024)
    assert "Año" in result.columns
    assert "Mes" in result.columns
    assert "Mes2" in result.columns
    assert set(result["Mes2"].unique()) == {"Abril", "Marzo"}


# ─── T14: conversión Cant Kg → Cant_Ton ──────────────────────────────────────

def test_cant_ton_es_cant_kg_dividido_1000():
    result = limpiar_base(_base_bronze(), ARTICULOS_IPC_TEST, "Abril", "Marzo", 2025, 2024)
    esperado = [1.0, 2.5, 3.0, 4.5]
    assert result["Cant_Ton"].tolist() == pytest.approx(esperado)


def test_cant_kg_invalido_lanza_error():
    df = _base_bronze()
    df["Cant Kg"] = ["abc", "500", "1000", "2000"]
    with pytest.raises(ValueError, match="no numericos"):
        limpiar_base(df, ARTICULOS_IPC_TEST, "Abril", "Marzo", 2025, 2024)


def test_cant_ton_directo():
    df = _base_bronze()
    _crear_cantidad_toneladas(df)
    assert df["Cant_Ton"].tolist() == pytest.approx([1.0, 2.5, 3.0, 4.5])


# ─── T16: mapeo Ali → Artículo_IPC / RArtículo_IPC ───────────────────────────

def test_mapea_variedades_y_codigos_ipc():
    result = limpiar_base(_base_bronze(), ARTICULOS_IPC_TEST, "Abril", "Marzo", 2025, 2024)
    assert result["Artículo_IPC"].tolist() == [
        "ARROZ",
        "LIMÓN",
        "BANANO",
        "CEBOLLA CABEZONA",
    ]
    assert result["RArtículo_IPC"].astype(int).tolist() == [1001, 1002, 1009, 1023]


def test_variedad_no_mapeada_produce_nulo():
    """T17: variedad fuera del diccionario → Artículo_IPC = NaN, no explota."""
    df = _base_bronze()
    df["Ali"] = ["ProductoDesconocido"] * 4
    result = limpiar_base(df, ARTICULOS_IPC_TEST, "Abril", "Marzo", 2025, 2024)
    assert result["Artículo_IPC"].isna().all()
    assert result["RArtículo_IPC"].isna().all()


def test_mapeo_insensible_a_mayusculas():
    """El lookup de variedades usa casefold: 'ARROZ' debe mapear como 'Arroz'."""
    df = _base_bronze()
    df["Ali"] = ["ARROZ", "LIMÓN TAHITÍ", "BANANO URABÁ", "CEBOLLA CABEZONA BLANCA"]
    result = limpiar_base(df, ARTICULOS_IPC_TEST, "Abril", "Marzo", 2025, 2024)
    assert result["Artículo_IPC"].tolist() == [
        "ARROZ",
        "LIMÓN",
        "BANANO",
        "CEBOLLA CABEZONA",
    ]


def test_mapeo_falla_sin_claves_requeridas():
    with pytest.raises(ValueError, match="variedades.*codigos|codigos.*variedades"):
        df = _base_bronze()
        _mapear_articulos_ipc(df, {"solo_codigos": {}})


# ─── T11: estandarización texto ──────────────────────────────────────────────

def test_estandariza_espacios_en_observaciones():
    result = limpiar_base(_base_bronze(), ARTICULOS_IPC_TEST, "Abril", "Marzo", 2025, 2024)
    assert result["Observaciones"].iloc[1] == "texto con espacios"


def test_normaliza_fechas_invalidas_lanza_error():
    """FechaEncuesta no convertible → ValueError."""
    df = _base_bronze()
    df["FechaEncuesta"] = ["not-a-date"] * 4
    with pytest.raises(ValueError, match="FechaEncuesta"):
        _normalizar_fechas(df)


# ─── T18: regresión numérica básica ──────────────────────────────────────────

def test_no_se_pierden_filas():
    """limpiar_base nunca filtra — todas las filas del bronze deben llegar."""
    df = _base_bronze()
    result = limpiar_base(df, ARTICULOS_IPC_TEST, "Abril", "Marzo", 2025, 2024)
    assert len(result) == len(df)


def test_columnas_nuevas_presentes():
    """F2 debe añadir exactamente las columnas esperadas."""
    result = limpiar_base(_base_bronze(), ARTICULOS_IPC_TEST, "Abril", "Marzo", 2025, 2024)
    nuevas = {"Ciudad", "Central", "Cant_Ton", "Mes2", "Año", "Mes", "PerFecha",
              "Artículo_IPC", "RArtículo_IPC"}
    for col in nuevas:
        assert col in result.columns, f"Falta columna de F2: {col}"
