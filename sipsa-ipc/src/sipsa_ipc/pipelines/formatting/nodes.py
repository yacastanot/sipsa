"""Nodos del pipeline de formato, normalización y ordenamiento — FASE 6.

Replica los data steps de adecuación y los PROC SORT del programa SAS original
SIPSA_A_MODELO_IPC.sas:

  /* TD_Abast */
  data TD_Abast;
    'Departamento Proc.'n = propcase('Departamento Proc.'n);
    if 'Departamento Proc.'n = "Valle Del Cauca"   then ... = "Valle del Cauca";
    if 'Departamento Proc.'n = "Norte De Santander" then ... = "Norte de Santander";
  run;
  proc sort data=TD_Abast; by RArtículo_IPC descending Participación;

  /* TD_Abast_Otros */
  data TD_Abast_Otros;
    'Municipio Proc.'n = propcase('Municipio Proc.'n);
    if 'Municipio Proc.'n = "Estados Unidos De América" then ... = "Estados Unidos de América";
  run;
  proc sort data=TD_Abast_Otros; by RArtículo_IPC descending Participación;

  /* TD_Destino — solo sort, Ciudad ya viene en formato correcto desde F2 */
  proc sort data=TD_Destino; by RArtículo_IPC descending Participación;
"""
from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)

# Correcciones explícitas post-propcase para departamentos colombianos.
# Replica los if/then del SAS: preposiciones en minúscula dentro del nombre.
_CORRECCIONES_DEPTOS: dict[str, str] = {
    "Valle Del Cauca":    "Valle del Cauca",
    "Norte De Santander": "Norte de Santander",
}

# Correcciones explícitas post-propcase para nombres de países en TD_Abast_Otros.
_CORRECCIONES_PAISES: dict[str, str] = {
    "Estados Unidos De América": "Estados Unidos de América",
}


def formatear_td_abast(td_abast: pd.DataFrame) -> pd.DataFrame:
    """Aplica PropCase a departamentos y ordena TD_Abast.

    Equivalente SAS:
        data TD_Abast; ... propcase('Departamento Proc.'n) ... run;
        proc sort data=TD_Abast;
            by 'RArtículo_IPC'n descending 'Participación'n;

    Args:
        td_abast: Tabla de abastecimiento de F4 con ``Departamento Proc.``
            en mayúsculas y ``Participación`` redondeada.

    Returns:
        DataFrame con departamentos en formato PropCase, corregidos y
        ordenados por ``RArtículo_IPC`` ASC, ``Participación`` DESC.
    """
    df = td_abast.copy()
    df["Departamento Proc."] = (
        df["Departamento Proc."]
        .astype(str)
        .map(_propcase_es)
        .replace(_CORRECCIONES_DEPTOS)
    )
    df = _ordenar(df)

    log.info(
        "formatear_td_abast OK | filas=%d | deptos_únicos=%d",
        len(df),
        df["Departamento Proc."].nunique(),
    )
    return df


def formatear_td_destino(td_destino: pd.DataFrame) -> pd.DataFrame:
    """Ordena TD_Destino por artículo y participación descendente.

    Ciudad ya viene en formato correcto desde F2 (creada a partir de Fuente),
    por lo que no se requiere PropCase adicional.

    Equivalente SAS:
        proc sort data=TD_Destino;
            by 'RArtículo_IPC'n descending 'Participación'n;

    Args:
        td_destino: Tabla de destino de F4.

    Returns:
        DataFrame ordenado por ``RArtículo_IPC`` ASC, ``Participación`` DESC.
    """
    df = _ordenar(td_destino.copy())

    log.info(
        "formatear_td_destino OK | filas=%d | ciudades=%d",
        len(df),
        df["Ciudad"].nunique(),
    )
    return df


def formatear_td_abast_otros(td_abast_otros: pd.DataFrame) -> pd.DataFrame:
    """Aplica PropCase a países de origen y ordena TD_Abast_Otros.

    Equivalente SAS:
        data TD_Abast_Otros;
            'Municipio Proc.'n = propcase('Municipio Proc.'n);
            if ... = "Estados Unidos De América" then ... = "Estados Unidos de América";
        run;
        proc sort data=TD_Abast_Otros;
            by 'RArtículo_IPC'n descending 'Participación'n;

    Args:
        td_abast_otros: Tabla de importaciones de F4. Puede estar vacía si
            no hay registros con Departamento Proc. = "n.a." en el mes actual.

    Returns:
        DataFrame con nombres de países en PropCase, corregidos y
        ordenados. DataFrame vacío si la entrada estaba vacía.
    """
    if td_abast_otros.empty:
        log.warning("formatear_td_abast_otros | Tabla de importaciones vacía.")
        return td_abast_otros.copy()

    df = td_abast_otros.copy()
    df["Municipio Proc."] = (
        df["Municipio Proc."]
        .astype(str)
        .map(_propcase_es)
        .replace(_CORRECCIONES_PAISES)
    )
    df = _ordenar(df)

    log.info(
        "formatear_td_abast_otros OK | filas=%d | paises=%d | articulos=%d",
        len(df),
        df["Municipio Proc."].nunique(),
        df["RArtículo_IPC"].nunique(),
    )
    return df


# ─── helpers privados ─────────────────────────────────────────────────────────

def _propcase_es(valor: str) -> str:
    """Convierte una cadena a PropCase (equivalente a SAS PROPCASE).

    Usa str.title() de Python, que capitaliza la primera letra de cada
    "palabra" (separada por espacios, puntos, comas, etc.) y convierte
    el resto a minúscula. Esto replica el comportamiento de SAS PROPCASE
    para textos en mayúsculas.

    Ejemplos:
        "CUNDINAMARCA"       → "Cundinamarca"
        "VALLE DEL CAUCA"    → "Valle Del Cauca"  (luego corregido)
        "BOGOTÁ, D.C."       → "Bogotá, D.C."
        "n.a."               → "N.A."
        "NORTE DE SANTANDER" → "Norte De Santander" (luego corregido)
    """
    return str(valor).title()


def _ordenar(df: pd.DataFrame) -> pd.DataFrame:
    """Ordena por RArtículo_IPC ASC y Participación DESC. Equivale al PROC SORT del SAS."""
    return (
        df.sort_values(
            ["RArtículo_IPC", "Participación"],
            ascending=[True, False],
        )
        .reset_index(drop=True)
    )
