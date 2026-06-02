"""Nodos del pipeline de limpieza - FASE 2.

Equivalente a la seccion posterior al PROC IMPORT en los programas SAS:
limpieza DIVIPOLA, parseo de Fuente, Cant_Ton, Mes2, PerFecha y mapeo
variedad SIPSA -> articulo IPC.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

MESES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

COLUMNAS_TEXTO = [
    "Fuente",
    "HoraEncuesta",
    "TipoVehiculo",
    "PlacaVehiculo",
    "Cod. Depto Proc.",
    "Departamento Proc.",
    "Cod. Municipio Proc.",
    "Municipio Proc.",
    "Observaciones",
    "Grupo",
    "Codigo CPC",
    "Ali",
    "Pres",
    "Digitador",
]


def limpiar_base(
    base_sipsa_bronze: pd.DataFrame,
    articulos_ipc: dict[str, Any],
    mes_actual_nombre: str,
    mes_anterior_nombre: str,
    anio_actual: int,
    anio_anterior: int,
) -> pd.DataFrame:
    """Construye la base limpia de F2 desde el snapshot bronze.

    Args:
        base_sipsa_bronze: Base importada y validada en F1.
        articulos_ipc: Diccionario YAML con variedades y codigos IPC.
        mes_actual_nombre: Mes actual configurado, por ejemplo ``Abril``.
        mes_anterior_nombre: Mes anterior configurado, por ejemplo ``Marzo``.
        anio_actual: Anio del periodo actual.
        anio_anterior: Anio usado para comparativo anual.

    Returns:
        DataFrame limpio con variables ``Ciudad``, ``Central``, ``Cant_Ton``,
        ``Mes2``, ``PerFecha``, ``Artículo_IPC`` y ``RArtículo_IPC``.
    """
    df = base_sipsa_bronze.copy()

    _estandarizar_texto(df)
    _normalizar_fechas(df)
    _limpiar_divipola(df)
    _crear_ciudad_y_central(df)
    _crear_periodo(
        df=df,
        mes_actual_nombre=mes_actual_nombre,
        mes_anterior_nombre=mes_anterior_nombre,
        anio_actual=anio_actual,
        anio_anterior=anio_anterior,
    )
    _crear_cantidad_toneladas(df)
    _mapear_articulos_ipc(df, articulos_ipc)

    log.info(
        "limpiar_base OK | filas=%d | mapeadas=%d | periodos=%s",
        len(df),
        int(df["RArtículo_IPC"].notna().sum()),
        df["PerFecha"].value_counts(dropna=False).to_dict(),
    )
    return df


def _estandarizar_texto(df: pd.DataFrame) -> None:
    """Aplica strip y compacta espacios en columnas de texto conocidas."""
    for columna in COLUMNAS_TEXTO:
        if columna not in df.columns:
            continue
        serie = df[columna]
        mascara = serie.notna()
        df.loc[mascara, columna] = (
            serie.loc[mascara]
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )


def _normalizar_fechas(df: pd.DataFrame) -> None:
    df["FechaEncuesta"] = pd.to_datetime(df["FechaEncuesta"], errors="coerce")
    n_fechas_invalidas = int(df["FechaEncuesta"].isna().sum())
    if n_fechas_invalidas:
        raise ValueError(
            f"FechaEncuesta contiene {n_fechas_invalidas} valores no convertibles."
        )


def _limpiar_divipola(df: pd.DataFrame) -> None:
    for columna in ("Cod. Depto Proc.", "Cod. Municipio Proc."):
        df[columna] = (
            df[columna]
            .astype("string")
            .str.replace("'", "", regex=False)
            .str.replace(r"\s+", "", regex=True)
        )


def _crear_ciudad_y_central(df: pd.DataFrame) -> None:
    fuente = df["Fuente"].astype("string").fillna("")
    partes = fuente.str.split(",", expand=True)

    ciudad1 = partes[0].str.strip()
    df["Ciudad"] = ciudad1.replace(
        {
            "Bogotá": "Bogotá, D.C.",
            "Ipiales (Nariño)": "Ipiales",
            "Santa Marta (Magdalena)": "Santa Marta",
        }
    )

    central1 = _parte_fuente(partes, 1)
    central2 = _parte_fuente(partes, 2)
    df["Central"] = central1.mask(central1.eq("") & central2.eq(""), fuente)
    df["Central"] = df["Central"].mask(central2.ne(""), central2)
    df["Central"] = df["Central"].astype("string").str.strip()


def _parte_fuente(partes: pd.DataFrame, posicion: int) -> pd.Series:
    if posicion in partes.columns:
        return partes[posicion].astype("string").fillna("").str.strip()
    return pd.Series("", index=partes.index, dtype="string")


def _crear_periodo(
    df: pd.DataFrame,
    mes_actual_nombre: str,
    mes_anterior_nombre: str,
    anio_actual: int,
    anio_anterior: int,
) -> None:
    mes_actual = _normalizar_mes(mes_actual_nombre)
    mes_anterior = _normalizar_mes(mes_anterior_nombre)

    df["Año"] = df["FechaEncuesta"].dt.year.astype("Int64")
    df["Mes"] = df["FechaEncuesta"].dt.month.astype("Int64")
    df["Mes2"] = df["Mes"].map(MESES_ES)

    df["PerFecha"] = pd.NA
    df.loc[
        (df["Año"].eq(anio_anterior)) & (df["Mes2"].map(_normalizar_mes).eq(mes_actual)),
        "PerFecha",
    ] = "Año anterior"
    df.loc[df["Mes2"].map(_normalizar_mes).eq(mes_anterior), "PerFecha"] = (
        "Mes anterior"
    )
    df.loc[
        (df["Año"].eq(anio_actual)) & (df["Mes2"].map(_normalizar_mes).eq(mes_actual)),
        "PerFecha",
    ] = "Mes actual"


def _crear_cantidad_toneladas(df: pd.DataFrame) -> None:
    cant_kg = pd.to_numeric(df["Cant Kg"], errors="coerce")
    invalidos = int(cant_kg.isna().sum() - df["Cant Kg"].isna().sum())
    if invalidos:
        raise ValueError(f"Cant Kg contiene {invalidos} valores no numericos.")
    df["Cant Kg"] = cant_kg
    df["Cant_Ton"] = cant_kg / 1000


def _mapear_articulos_ipc(df: pd.DataFrame, articulos_ipc: dict[str, Any]) -> None:
    variedades = articulos_ipc.get("variedades", {})
    codigos = articulos_ipc.get("codigos", {})

    if not variedades or not codigos:
        raise ValueError("articulos_ipc debe incluir las claves 'variedades' y 'codigos'.")

    lookup_variedades = {
        _normalizar_llave_variedad(variedad): _normalizar_articulo(articulo)
        for variedad, articulo in variedades.items()
    }
    lookup_codigos = {
        _normalizar_articulo(articulo): int(codigo)
        for articulo, codigo in codigos.items()
    }

    df["Artículo_IPC"] = df["Ali"].map(
        lambda valor: lookup_variedades.get(_normalizar_llave_variedad(valor))
    )
    df["RArtículo_IPC"] = df["Artículo_IPC"].map(lookup_codigos).astype("Int64")


def _normalizar_llave_variedad(valor: Any) -> str:
    if pd.isna(valor):
        return ""
    return str(valor).strip().casefold()


def _normalizar_articulo(valor: Any) -> str:
    if pd.isna(valor):
        return ""
    return str(valor).strip().upper()


def _normalizar_mes(valor: Any) -> str:
    return _normalizar_llave_variedad(valor)
