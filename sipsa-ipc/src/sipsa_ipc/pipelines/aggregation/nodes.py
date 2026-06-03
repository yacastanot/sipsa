"""Nodos del pipeline de agregación — FASE 4.

Replica exactamente los cuatro PROC SQL del programa SAS original
SIPSA_A_MODELO_IPC.sas:

  TD_Total      → SUM(Cant_Ton) por artículo en los 3 períodos.
  TD_Abast      → SUM(Cant_Ton) por artículo + departamento origen + Participación%.
  TD_Destino    → SUM(Cant_Ton) por artículo + ciudad destino + Participación%.
  TD_Abast_Otros→ SUM(Cant_Ton) importaciones (Depto=OTRO) por artículo + país + Participación%.

Las variaciones porcentuales (VariacMensual%, VariacAnual%) y el formato
decimal colombiano se calculan en F5.  El ordenamiento y el PropCase de
departamentos/países se aplican en F6.
"""
from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)

# Valor que aparece en los datos reales para registros de importación.
# El SAS original usaba "OTRO"; en la base Excel real el valor es "n.a."
DEPTO_IMPORTACIONES = "n.a."


def calcular_td_total(base_ipc_filtrada: pd.DataFrame) -> pd.DataFrame:
    """Genera TD_Total: abastecimiento total por artículo en los 3 períodos.

    Equivalente SAS:
        proc sql; create table Actual as select ...
        proc sql; create table MAnterior as select ...
        proc sql; create table AAnterior as select ...
        data TD_Total; merge Actual MAnterior AAnterior; by RArticulo_IPC;

    Args:
        base_ipc_filtrada: IPC2 — solo registros en canasta, con columna
            ``PerFecha`` = "Mes actual" | "Mes anterior" | "Año anterior".

    Returns:
        DataFrame con columnas:
            RArtículo_IPC, Artículo_IPC,
            AbastTotal_MesActual, AbastTotal_MesAnterior, AbastTotal_AnoAnterior.
    """
    mes_actual = _agrupar_por_articulo(base_ipc_filtrada, "Mes actual")
    mes_actual = mes_actual.rename(columns={"Sum_Ton": "AbastTotal_MesActual"})

    mes_anterior = (
        base_ipc_filtrada.loc[base_ipc_filtrada["PerFecha"].eq("Mes anterior")]
        .groupby("RArtículo_IPC", dropna=False)["Cant_Ton"]
        .sum()
        .reset_index()
        .rename(columns={"Cant_Ton": "AbastTotal_MesAnterior"})
    )

    anio_anterior = (
        base_ipc_filtrada.loc[base_ipc_filtrada["PerFecha"].eq("Año anterior")]
        .groupby("RArtículo_IPC", dropna=False)["Cant_Ton"]
        .sum()
        .reset_index()
        .rename(columns={"Cant_Ton": "AbastTotal_AnoAnterior"})
    )

    td = (
        mes_actual
        .merge(mes_anterior, on="RArtículo_IPC", how="outer")
        .merge(anio_anterior, on="RArtículo_IPC", how="outer")
        .sort_values("RArtículo_IPC")
        .reset_index(drop=True)
    )

    log.info(
        "calcular_td_total OK | articulos=%d | ton_mes_actual=%.1f",
        len(td),
        td["AbastTotal_MesActual"].sum(),
    )
    return td


def calcular_td_abast(base_ipc_filtrada: pd.DataFrame) -> pd.DataFrame:
    """Genera TD_Abast: toneladas por artículo y departamento de procedencia.

    Filtra Mes actual, suma por artículo + departamento y calcula
    Participación% = (Sum_Ton / Total_Artículo) * 100 redondeado a 2 decimales.

    Equivalente SAS:
        proc sql; create table TD_Abast1 ...
        proc sql; create table TD_Abast2 ...
        data TD_Abast; merge TD_Abast1 TD_Abast2; ...
        Participación = round(Sum_Ton*100/Total_Artículo, 0.01);

    Args:
        base_ipc_filtrada: IPC2 con columna ``Departamento Proc.``.

    Returns:
        DataFrame con columnas:
            RArtículo_IPC, Artículo_IPC, Departamento Proc.,
            Sum_Ton, Total_Artículo, Participación.
    """
    mes_act = base_ipc_filtrada.loc[base_ipc_filtrada["PerFecha"].eq("Mes actual")]

    detalle = (
        mes_act.groupby(
            ["RArtículo_IPC", "Artículo_IPC", "Departamento Proc."], dropna=False
        )["Cant_Ton"]
        .sum()
        .reset_index()
        .rename(columns={"Cant_Ton": "Sum_Ton"})
    )

    totales = (
        mes_act.groupby(["RArtículo_IPC", "Artículo_IPC"], dropna=False)["Cant_Ton"]
        .sum()
        .reset_index()
        .rename(columns={"Cant_Ton": "Total_Artículo"})
    )

    td = detalle.merge(totales, on=["RArtículo_IPC", "Artículo_IPC"], how="left")
    td["Participación"] = (td["Sum_Ton"] * 100 / td["Total_Artículo"]).round(2)

    log.info(
        "calcular_td_abast OK | filas=%d | articulos=%d",
        len(td),
        td["RArtículo_IPC"].nunique(),
    )
    return td


def calcular_td_destino(base_ipc_filtrada: pd.DataFrame) -> pd.DataFrame:
    """Genera TD_Destino: toneladas por artículo y ciudad de destino.

    Filtra Mes actual, suma por artículo + Ciudad y calcula Participación%.

    Equivalente SAS:
        proc sql; create table TD_Destino1 ...
        proc sql; create table TD_Destino2 ...
        data TD_Destino; Participación = round(..., 0.01);

    Args:
        base_ipc_filtrada: IPC2 con columna ``Ciudad`` creada en F2.

    Returns:
        DataFrame con columnas:
            RArtículo_IPC, Artículo_IPC, Ciudad,
            Sum_Ton, Total_Artículo, Participación.
    """
    mes_act = base_ipc_filtrada.loc[base_ipc_filtrada["PerFecha"].eq("Mes actual")]

    detalle = (
        mes_act.groupby(
            ["RArtículo_IPC", "Artículo_IPC", "Ciudad"], dropna=False
        )["Cant_Ton"]
        .sum()
        .reset_index()
        .rename(columns={"Cant_Ton": "Sum_Ton"})
    )

    totales = (
        mes_act.groupby(["RArtículo_IPC", "Artículo_IPC"], dropna=False)["Cant_Ton"]
        .sum()
        .reset_index()
        .rename(columns={"Cant_Ton": "Total_Artículo"})
    )

    td = detalle.merge(totales, on=["RArtículo_IPC", "Artículo_IPC"], how="left")
    td["Participación"] = (td["Sum_Ton"] * 100 / td["Total_Artículo"]).round(2)

    log.info(
        "calcular_td_destino OK | filas=%d | ciudades=%d | articulos=%d",
        len(td),
        td["Ciudad"].nunique(),
        td["RArtículo_IPC"].nunique(),
    )
    return td


def calcular_td_abast_otros(base_ipc_filtrada: pd.DataFrame) -> pd.DataFrame:
    """Genera TD_Abast_Otros: importaciones por artículo y país de origen.

    Filtra Mes actual y Departamento Proc. = "OTRO" (registros de importación).
    Suma por artículo + Municipio Proc. (contiene el país de origen) y calcula
    Participación% dentro de cada artículo.

    Equivalente SAS:
        proc sql; create table TD_Abast_Otros1 ...
        (where PerFecha="Mes actual" and Departamento Proc.="OTRO")
        proc sql; create table TD_Abast_Otros2 ...
        data TD_Abast_Otros; Participación = round(..., 0.01);

    Args:
        base_ipc_filtrada: IPC2 con columnas ``Departamento Proc.``
            y ``Municipio Proc.``.

    Returns:
        DataFrame con columnas:
            RArtículo_IPC, Artículo_IPC, Municipio Proc.,
            Sum_Ton, Total_Artículo, Participación.
        Vacío si no existen registros de importación en el mes actual.
    """
    importaciones = base_ipc_filtrada.loc[
        base_ipc_filtrada["PerFecha"].eq("Mes actual")
        & base_ipc_filtrada["Departamento Proc."].eq(DEPTO_IMPORTACIONES)
    ]

    if importaciones.empty:
        log.warning(
            "calcular_td_abast_otros | Sin registros con Departamento Proc.='%s' en Mes actual.",
            DEPTO_IMPORTACIONES,
        )
        return pd.DataFrame(
            columns=[
                "RArtículo_IPC", "Artículo_IPC", "Municipio Proc.",
                "Sum_Ton", "Total_Artículo", "Participación",
            ]
        )

    detalle = (
        importaciones.groupby(
            ["RArtículo_IPC", "Artículo_IPC", "Municipio Proc."], dropna=False
        )["Cant_Ton"]
        .sum()
        .reset_index()
        .rename(columns={"Cant_Ton": "Sum_Ton"})
    )

    totales = (
        importaciones.groupby(["RArtículo_IPC", "Artículo_IPC"], dropna=False)["Cant_Ton"]
        .sum()
        .reset_index()
        .rename(columns={"Cant_Ton": "Total_Artículo"})
    )

    td = detalle.merge(totales, on=["RArtículo_IPC", "Artículo_IPC"], how="left")
    td["Participación"] = (td["Sum_Ton"] * 100 / td["Total_Artículo"]).round(2)

    log.info(
        "calcular_td_abast_otros OK | filas=%d | articulos=%d | paises=%d",
        len(td),
        td["RArtículo_IPC"].nunique(),
        td["Municipio Proc."].nunique(),
    )
    return td


# ─── helpers privados ─────────────────────────────────────────────────────────

def _agrupar_por_articulo(df: pd.DataFrame, periodo: str) -> pd.DataFrame:
    """Suma Cant_Ton por artículo para un período específico."""
    return (
        df.loc[df["PerFecha"].eq(periodo)]
        .groupby(["RArtículo_IPC", "Artículo_IPC"], dropna=False)["Cant_Ton"]
        .sum()
        .reset_index()
        .rename(columns={"Cant_Ton": "Sum_Ton"})
    )
