"""Nodos del pipeline de validación — FASE 3.

Equivalente SAS:
  /* IPC2: solo artículos en canasta */
  data IPC2;
    set IPC1;
    where RArticulo_IPC ne .;
  run;

  proc sort data=IPC2; by RArticulo_IPC; run;

  /* No mapeados: variedades sin código IPC */
  proc freq data=IPC1;
    where RArticulo_IPC = .;
    tables Ali / out=No_mapeados_IPC;
  run;

  /* Cobertura: artículos con al menos un registro vs canasta completa */
  proc sql;
    create table Cobertura as
    select distinct RArticulo_IPC, Articulo_IPC
    from IPC2;
  quit;
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


def filtrar_articulos_canasta(base_sipsa_clean: pd.DataFrame) -> pd.DataFrame:
    """Retiene solo registros con RArtículo_IPC mapeado (IPC2 en SAS).

    Args:
        base_sipsa_clean: DataFrame limpio de F2, con columnas
            ``RArtículo_IPC`` y ``Artículo_IPC``.

    Returns:
        DataFrame IPC2 con únicamente los registros en canasta IPC,
        ordenado por RArtículo_IPC.
    """
    mascara = base_sipsa_clean["RArtículo_IPC"].notna()
    ipc2 = base_sipsa_clean.loc[mascara].copy()
    ipc2 = ipc2.sort_values("RArtículo_IPC").reset_index(drop=True)

    n_total = len(base_sipsa_clean)
    n_filtrados = len(ipc2)
    n_excluidos = n_total - n_filtrados

    log.info(
        "filtrar_articulos_canasta OK | total=%d | en_canasta=%d | excluidos=%d (%.1f%%)",
        n_total,
        n_filtrados,
        n_excluidos,
        100 * n_excluidos / n_total if n_total else 0,
    )
    return ipc2


def generar_no_mapeados(base_sipsa_clean: pd.DataFrame) -> pd.DataFrame:
    """Construye la tabla de variedades SIPSA sin mapeo a artículo IPC.

    Equivalente al ``proc freq`` en SAS sobre los registros con
    ``RArticulo_IPC = .``.  Genera una fila por variedad única no mapeada
    con su frecuencia total de registros.

    Args:
        base_sipsa_clean: DataFrame limpio de F2.

    Returns:
        DataFrame con columnas:
            - ``Ali``: variedad del alimento (texto tal como viene del Excel).
            - ``Grupo``: grupo de alimento.
            - ``N_Registros``: total de filas con esa variedad.
        Ordenado por ``N_Registros`` descendente.
    """
    sin_mapeo = base_sipsa_clean.loc[base_sipsa_clean["RArtículo_IPC"].isna()]

    if sin_mapeo.empty:
        log.info("generar_no_mapeados | Sin variedades no mapeadas.")
        return pd.DataFrame(columns=["Ali", "Grupo", "N_Registros"])

    conteo = (
        sin_mapeo.groupby(["Ali", "Grupo"], dropna=False)
        .size()
        .reset_index(name="N_Registros")
        .sort_values("N_Registros", ascending=False)
        .reset_index(drop=True)
    )

    log.info(
        "generar_no_mapeados OK | variedades_no_mapeadas=%d | registros_afectados=%d",
        len(conteo),
        int(conteo["N_Registros"].sum()),
    )
    return conteo


def calcular_cobertura(
    base_ipc_filtrada: pd.DataFrame,
    articulos_ipc: dict[str, Any],
    mes_actual_nombre: str,
    anio_actual: int,
) -> pd.DataFrame:
    """Calcula la cobertura de la canasta IPC para el mes actual.

    Para cada uno de los 29 artículos IPC definidos en el diccionario,
    reporta cuántos registros de ``Mes actual`` existen en la base filtrada.
    Un artículo con N=0 indica ausencia de datos para ese período.

    Args:
        base_ipc_filtrada: DataFrame IPC2 (solo registros en canasta).
        articulos_ipc: Diccionario YAML con ``codigos`` y ``variedades``.
        mes_actual_nombre: Nombre del mes actual (ej: ``"Abril"``).
        anio_actual: Año del período actual.

    Returns:
        DataFrame con columnas:
            - ``RArtículo_IPC``: código numérico del artículo (1001–1029).
            - ``Artículo_IPC``: nombre del artículo IPC.
            - ``N_Registros_MesActual``: registros en el mes actual.
            - ``Tiene_Cobertura``: True si N_Registros_MesActual > 0.
        Más una fila resumen al final con el total de artículos cubiertos.
    """
    codigos: dict[str, int] = articulos_ipc.get("codigos", {})

    canasta = pd.DataFrame(
        [
            {"Artículo_IPC": articulo.strip().upper(), "RArtículo_IPC": int(codigo)}
            for articulo, codigo in codigos.items()
        ]
    ).sort_values("RArtículo_IPC").reset_index(drop=True)

    mes_actual = base_ipc_filtrada.loc[
        base_ipc_filtrada["PerFecha"].eq("Mes actual")
    ]

    conteo_mes = (
        mes_actual.groupby("RArtículo_IPC")
        .size()
        .reset_index(name="N_Registros_MesActual")
    )
    conteo_mes["RArtículo_IPC"] = conteo_mes["RArtículo_IPC"].astype("Int64")

    cobertura = canasta.merge(conteo_mes, on="RArtículo_IPC", how="left")
    cobertura["N_Registros_MesActual"] = (
        cobertura["N_Registros_MesActual"].fillna(0).astype(int)
    )
    cobertura["Tiene_Cobertura"] = cobertura["N_Registros_MesActual"].gt(0)

    n_cubiertos = int(cobertura["Tiene_Cobertura"].sum())
    n_total = len(cobertura)

    log.info(
        "calcular_cobertura OK | mes=%s %d | articulos_cubiertos=%d/%d (%.1f%%)",
        mes_actual_nombre,
        anio_actual,
        n_cubiertos,
        n_total,
        100 * n_cubiertos / n_total if n_total else 0,
    )
    return cobertura
