"""Nodos del pipeline de generación de reportes — FASE 7.

Produce tres salidas equivalentes al programa SAS original:

  T38  SIPSA_IPC_YYYYMMDD.xlsx       — 4 hojas: TD_Total, TD_Abast,
                                         TD_Destino, TD_Abast_Otros.
  T39  Alimentos_priorizados_*.xlsx  — resumen de artículos por mes,
                                         con zonas y destinos en texto.
  T40  historico_td_total.parquet    — acumulado mensual de TD_Total.

Equivalente SAS (T38):
  %macro exporta(data);
  proc export data=&data. outfile="&salida./SIPSA_IPC_&f..xlsx"
              dbms=xlsx replace; sheet="&data."; run;
  %mend;
  %exporta(TD_Total); %exporta(TD_Abast);
  %exporta(TD_Destino); %exporta(TD_Abast_Otros);
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# Columnas que se exportan en cada hoja del Excel principal.
# Se excluyen las columnas intermedias (_num) que no forman parte del output SAS.
_COLS_TD_TOTAL = [
    "RArtículo_IPC", "Artículo_IPC",
    "AbastTotal_MesActual", "AbastTotal_MesAnterior", "AbastTotal_AnoAnterior",
    "VariacMensual", "VariacAnual",
]
_COLS_TD_ABAST = [
    "RArtículo_IPC", "Artículo_IPC", "Departamento Proc.",
    "Sum_Ton", "Total_Artículo", "Participación",
]
_COLS_TD_DESTINO = [
    "RArtículo_IPC", "Artículo_IPC", "Ciudad",
    "Sum_Ton", "Total_Artículo", "Participación",
]
_COLS_TD_ABAST_OTROS = [
    "RArtículo_IPC", "Artículo_IPC", "Municipio Proc.",
    "Sum_Ton", "Total_Artículo", "Participación",
]

# Número máximo de entradas que se muestran en las celdas de texto del
# reporte Alimentos priorizados (zonas y destinos).
_MAX_ENTRADAS_TEXTO = 15


# ─── T38: SIPSA_IPC_YYYYMMDD.xlsx ─────────────────────────────────────────────

def exportar_sipsa_ipc(
    td_total_variaciones: pd.DataFrame,
    td_abast_fmt: pd.DataFrame,
    td_destino_fmt: pd.DataFrame,
    td_abast_otros_fmt: pd.DataFrame,
    fecha_proceso: str,
    ruta_reporting: str,
) -> pd.DataFrame:
    """Genera SIPSA_IPC_YYYYMMDD.xlsx con 4 hojas.

    Replica exactamente el macro ``%exporta`` del programa SAS original.
    Las columnas intermedias (VariacMensual_num, VariacAnual_num) se omiten
    de la hoja TD_Total, conservando únicamente las columnas presentes en el
    output SAS de referencia.

    Args:
        td_total_variaciones: TD_Total con variaciones (F5).
        td_abast_fmt: TD_Abast formateada y ordenada (F6).
        td_destino_fmt: TD_Destino ordenada (F6).
        td_abast_otros_fmt: TD_Abast_Otros formateada y ordenada (F6).
        fecha_proceso: Cadena YYYYMMDD que forma parte del nombre del archivo.
        ruta_reporting: Directorio de destino (relativo al proyecto).

    Returns:
        DataFrame de una fila con metadatos del archivo exportado.
    """
    Path(ruta_reporting).mkdir(parents=True, exist_ok=True)
    filepath = Path(ruta_reporting) / f"SIPSA_IPC_{fecha_proceso}.xlsx"

    hojas = {
        "TD_Total":       td_total_variaciones[_COLS_TD_TOTAL],
        "TD_Abast":       td_abast_fmt[_COLS_TD_ABAST],
        "TD_Destino":     td_destino_fmt[_COLS_TD_DESTINO],
        "TD_Abast_Otros": td_abast_otros_fmt[_COLS_TD_ABAST_OTROS],
    }

    with pd.ExcelWriter(str(filepath), engine="openpyxl") as writer:
        for nombre_hoja, df_hoja in hojas.items():
            df_hoja.to_excel(writer, sheet_name=nombre_hoja, index=False)

    filas_total = sum(len(df) for df in hojas.values())
    log.info(
        "exportar_sipsa_ipc OK | archivo=%s | hojas=%d | filas_totales=%d",
        filepath.name,
        len(hojas),
        filas_total,
    )
    return pd.DataFrame([{
        "archivo": str(filepath),
        "hojas": len(hojas),
        "filas_td_total": len(hojas["TD_Total"]),
        "filas_td_abast": len(hojas["TD_Abast"]),
        "filas_td_destino": len(hojas["TD_Destino"]),
        "filas_td_abast_otros": len(hojas["TD_Abast_Otros"]),
    }])


# ─── T39: Alimentos_priorizados_*.xlsx ────────────────────────────────────────

def exportar_alimentos_priorizados(
    td_total_variaciones: pd.DataFrame,
    td_abast_fmt: pd.DataFrame,
    td_destino_fmt: pd.DataFrame,
    td_abast_otros_fmt: pd.DataFrame,
    mes_actual_nombre: str,
    anio_actual: int,
    fecha_proceso: str,
    ruta_reporting: str,
) -> pd.DataFrame:
    """Genera Alimentos_priorizados_MES-AA_SIPSA_YYYYMMDD.xlsx.

    Produce un resumen tabulado con una fila por artículo IPC que incluye:
    - Abastecimiento en los 3 períodos y variaciones porcentuales.
    - Texto multilinea con las principales zonas abastecedoras.
    - Texto multilinea con los principales destinos de consumo.
    - Texto multilinea con las importaciones (si las hay).

    Args:
        td_total_variaciones: TD_Total con variaciones (F5).
        td_abast_fmt: TD_Abast formateada (F6).
        td_destino_fmt: TD_Destino formateada (F6).
        td_abast_otros_fmt: TD_Abast_Otros formateada (F6).
        mes_actual_nombre: Nombre español del mes actual (ej: ``"Abril"``).
        anio_actual: Año del período actual.
        fecha_proceso: Cadena YYYYMMDD para el nombre del archivo.
        ruta_reporting: Directorio de destino.

    Returns:
        DataFrame de una fila con metadatos del archivo exportado.
    """
    Path(ruta_reporting).mkdir(parents=True, exist_ok=True)
    anio_corto = str(anio_actual)[-2:]
    mes_corto = mes_actual_nombre[:3].lower()
    nombre = f"Alimentos_priorizados_{mes_corto}{anio_corto}_SIPSA_{fecha_proceso}.xlsx"
    filepath = Path(ruta_reporting) / nombre

    resumen = _construir_resumen(
        td_total_variaciones, td_abast_fmt, td_destino_fmt, td_abast_otros_fmt
    )

    with pd.ExcelWriter(str(filepath), engine="openpyxl") as writer:
        resumen.to_excel(writer, sheet_name="Artículos_IPC", index=False)

    log.info(
        "exportar_alimentos_priorizados OK | archivo=%s | articulos=%d",
        nombre,
        len(resumen),
    )
    return pd.DataFrame([{"archivo": str(filepath), "articulos": len(resumen)}])


def _construir_resumen(
    td_total: pd.DataFrame,
    td_abast: pd.DataFrame,
    td_destino: pd.DataFrame,
    td_otros: pd.DataFrame,
) -> pd.DataFrame:
    """Construye el DataFrame tabulado del reporte de artículos priorizados."""
    base = td_total[_COLS_TD_TOTAL + ["VariacMensual_num", "VariacAnual_num"]].copy()

    zonas = _texto_zonas(td_abast, td_otros)
    destinos = _texto_destinos(td_destino)

    resumen = base.merge(zonas, on="RArtículo_IPC", how="left")
    resumen = resumen.merge(destinos, on="RArtículo_IPC", how="left")

    resumen = resumen.rename(columns={
        "VariacMensual_num": "Variacion mensual",
        "VariacAnual_num":   "Variacion anual",
        "Zonas abastecedoras": "Zonas abastecedoras",
        "Destino": "Destino de los alimentos",
    })
    return resumen[[
        "RArtículo_IPC", "Artículo_IPC",
        "Zonas abastecedoras", "Destino de los alimentos",
        "AbastTotal_MesActual", "AbastTotal_MesAnterior", "AbastTotal_AnoAnterior",
        "Variacion mensual", "Variacion anual",
    ]]


def _texto_zonas(td_abast: pd.DataFrame, td_otros: pd.DataFrame) -> pd.DataFrame:
    """Genera texto multilinea de zonas abastecedoras por artículo.

    Para cada artículo concatena: "{Depto}  {P,2dec%}\\n..."
    Las filas con Departamento Proc. = "N.A." se reemplazan por
    "N.A. ({País1, País2, ...})  {P%}" usando los datos de TD_Abast_Otros.
    """
    filas = []
    paises_por_art = _construir_lookup_paises(td_otros)

    for cod, grp in td_abast.groupby("RArtículo_IPC", sort=True):
        partes: list[str] = []
        participacion_na = 0.0

        for _, fila in grp.head(_MAX_ENTRADAS_TEXTO).iterrows():
            depto = fila["Departamento Proc."]
            p = fila["Participación"]
            if depto == "N.A.":
                participacion_na = p
                paises = paises_por_art.get(int(cod), [])
                etiqueta_paises = ", ".join(paises) if paises else ""
                parte = f"N.A. ({etiqueta_paises})   {_fmt_pct(p)}"
            else:
                parte = f"{depto}  {_fmt_pct(p)}"
            partes.append(parte)

        filas.append({"RArtículo_IPC": cod, "Zonas abastecedoras": "\n".join(partes)})

    return pd.DataFrame(filas)


def _texto_destinos(td_destino: pd.DataFrame) -> pd.DataFrame:
    """Genera texto multilinea de destinos de consumo por artículo."""
    filas = []
    for cod, grp in td_destino.groupby("RArtículo_IPC", sort=True):
        partes = [
            f"{r['Ciudad']}  {_fmt_pct(r['Participación'])}"
            for _, r in grp.head(_MAX_ENTRADAS_TEXTO).iterrows()
        ]
        filas.append({"RArtículo_IPC": cod, "Destino": "\n".join(partes)})
    return pd.DataFrame(filas)


def _construir_lookup_paises(td_otros: pd.DataFrame) -> dict[int, list[str]]:
    """Dict artículo → lista de países de importación ordenados por Participación."""
    if td_otros.empty:
        return {}
    lookup: dict[int, list[str]] = {}
    for cod, grp in td_otros.groupby("RArtículo_IPC", sort=True):
        paises = grp.sort_values("Participación", ascending=False)["Municipio Proc."].tolist()
        lookup[int(cod)] = paises
    return lookup


def _fmt_pct(valor: float) -> str:
    """Formatea un porcentaje con coma decimal y 2 decimales. Ej: ``24,07%``."""
    return f"{valor:.2f}".replace(".", ",") + "%"


# ─── T40: Histórico mensual en Parquet ────────────────────────────────────────

def guardar_historico(
    td_total_variaciones: pd.DataFrame,
    mes_actual_nombre: str,
    anio_actual: int,
) -> pd.DataFrame:
    """Agrega el mes actual al acumulado histórico mensual de TD_Total.

    Añade columnas ``mes`` y ``anio`` para identificar el período y retorna
    el registro completo para ser persisitido por Kedro como Parquet.

    Args:
        td_total_variaciones: TD_Total con variaciones del mes actual (F5).
        mes_actual_nombre: Nombre del mes (ej: ``"Abril"``).
        anio_actual: Año del período actual.

    Returns:
        DataFrame con columnas adicionales ``mes`` y ``anio``.
    """
    df = td_total_variaciones[_COLS_TD_TOTAL + ["VariacMensual_num", "VariacAnual_num"]].copy()
    df["mes"] = mes_actual_nombre
    df["anio"] = anio_actual

    log.info(
        "guardar_historico OK | mes=%s %d | articulos=%d",
        mes_actual_nombre,
        anio_actual,
        len(df),
    )
    return df
