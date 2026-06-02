"""Nodos del pipeline Fletes.

Migración de Fletes-EMCES.R (R + tidyverse + openxlsx) a Python/Kedro.

Secciones del script R:
  7  → preparar_m49
  8-10 → unir_fletes_m49
  11-12 → enriquecer_con_referencias
  13 → construir_registro_maestro
  14 → exportar_excel
"""
from __future__ import annotations

import logging
import os
import re

import pandas as pd

from emces.strategies.via_strategy import apply_via_strategy

logger = logging.getLogger(__name__)

# Orden final de columnas — replica exactamente el vector `orden_final` del script R
ORDEN_FINAL = [
    "flujo_comercial", "idnoremp", "periodo", "mes", "periodo_mes", "sede", "csede",
    "idact", "idnitcc", "iddv", "razsoc", "nombre", "sigla", "direccion",
    "idmpio", "nom_mpio", "iddepto", "nom_depto", "telefono", "ext", "celular", "filial",
    "rep_legal", "celular_rep_legal", "telefono_rep_legal", "ext_rep_legal",
    "idmail_rep_legal", "idmail_rep_legalconf", "contacto", "cargo", "idtel2",
    "idtel3", "idtelext2", "idcel_2", "idcel_3", "idmail3", "idmail3conf", "idmail4",
    "idmail4conf", "agrupacion", "descripcion_grupo", "codigo", "descripcion_cabps",
    "cpc", "descripcion_cpc", "nombre_departamento", "departamento", "pais",
    "nombre_pais", "pais_cod_iso_3166", "pais_cod_alpha_3", "acuerdo_1", "acuerdo_2",
    "acuerdo_3", "vrocefats", "vroce", "construccion", "total_en_miles_de_pesos",
    "trm_base", "total_en_dolares", "total_vrocefats_dolares",
    "total_vroce_dolares", "total_construccion_dolares", "modo", "descripcion_modo",
    "observacion", "id", "nom_estado", "novedad", "ociser", "justificacion_critico",
    "justificacion_logistico", "justificacion_supervisor",
]


# ── Helpers de lectura ────────────────────────────────────────────────────────

def _limpiar_nombres(df: pd.DataFrame) -> pd.DataFrame:
    def _clean(name: str) -> str:
        name = name.strip().lower()
        name = re.sub(r"[^a-z0-9]+", "_", name)
        return name.strip("_")
    df.columns = [_clean(c) for c in df.columns]
    return df


def _leer_excel(ruta: str, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(ruta, sheet_name=sheet, dtype=str)
    df = df.apply(lambda col: col.str.strip().replace("", pd.NA) if col.dtype == object else col)
    return df


# ── Ingesta ───────────────────────────────────────────────────────────────────

def leer_pais(ruta_entrada: str, archivo_parametricas: str) -> pd.DataFrame:
    ruta = os.path.join(ruta_entrada, archivo_parametricas)
    df = _limpiar_nombres(_leer_excel(ruta, sheet="T_P_PAIS-ACUERDOS"))
    logger.info("raw_pais: %d filas, %d columnas", len(df), len(df.columns))
    return df


def leer_trm(ruta_entrada: str, archivo_parametricas: str) -> pd.DataFrame:
    ruta = os.path.join(ruta_entrada, archivo_parametricas)
    df = _limpiar_nombres(_leer_excel(ruta, sheet="T_P_TRM_2022"))
    df = df[["periodo", "mes", "trm_base"]]
    logger.info("raw_trm: %d filas", len(df))
    return df


def leer_fletes(
    ruta_entrada: str,
    archivo_fletes: str,
    ano: str,
    mes_numero: str,
) -> pd.DataFrame:
    ruta = os.path.join(ruta_entrada, archivo_fletes)
    df = _limpiar_nombres(_leer_excel(ruta, sheet="BAND"))
    logger.info("raw_fletes (%s-%s): %d filas", ano, mes_numero, len(df))
    return df


def leer_m49(ruta_entrada: str, archivo_parametricas: str) -> pd.DataFrame:
    ruta = os.path.join(ruta_entrada, archivo_parametricas)
    df = _limpiar_nombres(_leer_excel(ruta, sheet="Fletes_M49"))
    logger.info("raw_m49: %d filas", len(df))
    return df


# ── Transformación ────────────────────────────────────────────────────────────

def preparar_m49(df_m49_raw: pd.DataFrame) -> pd.DataFrame:
    # La hoja Fletes_M49 tiene 'Código_ALADI' → clean_names → 'c_digo_aladi'
    df = df_m49_raw[["m49_code", "c_digo_aladi"]].copy()
    df["m49_code"] = df["m49_code"].str.strip()
    df["c_digo_aladi"] = df["c_digo_aladi"].str.strip()
    df = df.rename(columns={"m49_code": "m49", "c_digo_aladi": "band"})
    df["m49"] = pd.to_numeric(df["m49"], errors="coerce")
    df["band"] = pd.to_numeric(df["band"], errors="coerce")
    df = df.dropna(subset=["m49", "band"])
    logger.info("m49_limpio: %d pares m49<->band", len(df))
    return df


def unir_fletes_m49(
    df_fletes_raw: pd.DataFrame,
    df_m49: pd.DataFrame,
    band_excluir: dict,
    ano: str,
) -> pd.DataFrame:
    excluir: list[int] = band_excluir.get("band_excluir", [])
    col_flet = f"tot_flet{ano}"

    df = df_fletes_raw.copy()
    if "band" in df.columns:
        df = df.rename(columns={"band": "m49"})

    df["m49"] = pd.to_numeric(df["m49"].str.strip(), errors="coerce")
    df = df.merge(df_m49, on="m49", how="left")

    if col_flet not in df.columns:
        available = [c for c in df.columns if c.startswith("tot_flet")]
        raise KeyError(f"Columna '{col_flet}' no encontrada. Disponibles: {available}")

    df = df[["band", "mes", "via", col_flet]].copy()
    df = df.rename(columns={col_flet: "tot_flet"})

    df["band"] = pd.to_numeric(df["band"], errors="coerce")
    df["via"] = pd.to_numeric(df["via"], errors="coerce")
    df = df[~df["band"].isin(excluir)]
    df = df[df["via"].isin([1, 3, 4])]
    df = df.rename(columns={"band": "pais"})

    df["tot_flet"] = pd.to_numeric(df["tot_flet"].astype(str).str.strip(), errors="coerce")
    df_agg = (
        df.groupby(["mes", "pais", "via"], dropna=False)
        .agg(flet_mes=("tot_flet", "sum"))
        .reset_index()
    )
    logger.info("fletes_filtrados: %d filas tras exclusión/filtro/agrupación", len(df_agg))
    return df_agg


# ── Construcción ──────────────────────────────────────────────────────────────

def enriquecer_con_referencias(
    df_fletes_filtrados: pd.DataFrame,
    df_pais: pd.DataFrame,
    df_trm: pd.DataFrame,
    ano: str,
    mes_numero: str,
) -> pd.DataFrame:
    df = df_fletes_filtrados.copy()

    df["pais"] = df["pais"].astype(str)
    df_pais_str = df_pais.copy()
    df_pais_str["pais"] = df_pais_str["pais"].astype(str)
    df = df.merge(df_pais_str, on="pais", how="left")

    df["periodo"] = ano

    df_trm_local = df_trm.copy()
    df_trm_local["periodo"] = df_trm_local["periodo"].astype(str)
    df_trm_local["mes"] = df_trm_local["mes"].astype(str)
    df["mes"] = df["mes"].astype(str)
    df = df.merge(df_trm_local, on=["periodo", "mes"], how="left")

    df["trm_base"] = pd.to_numeric(df["trm_base"], errors="coerce")
    logger.info("fletes_enriquecidos: %d filas tras joins con PAIS y TRM", len(df))
    return df


def construir_registro_maestro(df_enriquecido: pd.DataFrame) -> pd.DataFrame:
    df = df_enriquecido.copy()

    df["flujo_comercial"] = "IMPORTACIONES FLETES"
    df["idnoremp"] = "777-1"
    df["periodo_mes"] = df["periodo"].astype(str) + "_" + df["mes"].astype(str)
    df["sede"] = "NA"
    df["csede"] = 0
    df["agrupacion"] = 3
    df["descripcion_grupo"] = "Servicios de transporte"
    df["nombre_departamento"] = "NA"
    df["departamento"] = 0
    df["vrocefats"] = 0
    df["vroce"] = 0
    df["construccion"] = 0
    df["total_vrocefats_dolares"] = 0
    df["total_vroce_dolares"] = 0
    df["total_construccion_dolares"] = 0
    df["modo"] = 1
    df["descripcion_modo"] = (
        "El proveedor y consumidor permanecen en sus respectivos territorios, "
        "solo se desplaza el servicio."
    )
    df["id"] = "NA"
    df["nom_estado"] = "NA"
    df["novedad"] = 99
    df["ociser"] = 1

    campos_vacios = [
        "idact", "idnitcc", "iddv", "razsoc", "nombre", "sigla", "direccion",
        "idmpio", "nom_mpio", "iddepto", "nom_depto", "telefono", "ext", "celular",
        "filial", "rep_legal", "celular_rep_legal", "telefono_rep_legal",
        "ext_rep_legal", "idmail_rep_legal", "idmail_rep_legalconf", "contacto",
        "cargo", "idtel2", "idtel3", "idtelext2", "idcel_2", "idcel_3",
        "idmail3", "idmail3conf", "idmail4", "idmail4conf",
        "observacion", "justificacion_critico", "justificacion_logistico",
        "justificacion_supervisor",
    ]
    for campo in campos_vacios:
        df[campo] = " "

    df["total_en_dolares"] = pd.to_numeric(df["flet_mes"], errors="coerce") / 1000
    df["total_en_miles_de_pesos"] = df["total_en_dolares"] / df["trm_base"]

    df["pais"] = pd.to_numeric(df["pais"], errors="coerce")
    if "pais_cod_iso_3166" in df.columns:
        df["pais_cod_iso_3166"] = pd.to_numeric(df["pais_cod_iso_3166"], errors="coerce")

    obj_cols = df.select_dtypes(include="object").columns
    df[obj_cols] = df[obj_cols].fillna("")

    antes = len(df)
    df = df[df["total_en_dolares"].notna() & (df["total_en_dolares"] != 0)]
    logger.info("Filtradas %d filas con total_en_dolares = 0 o NaN", antes - len(df))

    df["via"] = pd.to_numeric(df["via"], errors="coerce")
    df = apply_via_strategy(df)

    for col in ORDEN_FINAL:
        if col not in df.columns:
            df[col] = ""

    df = df[ORDEN_FINAL]
    logger.info("fletes_maestro: %d filas finales", len(df))
    return df


# ── Reporting ─────────────────────────────────────────────────────────────────

def exportar_excel(
    df_maestro: pd.DataFrame,
    ano: str,
    mes_numero: str,
    ruta_salida: str,
) -> dict:
    nombre_hoja = f"Fletes_EMCES_{ano}_{mes_numero}"
    nombre_archivo = f"{nombre_hoja}.xlsx"
    ruta_completa = os.path.join(ruta_salida, nombre_archivo)

    os.makedirs(ruta_salida, exist_ok=True)

    df_out = df_maestro.rename(columns=str.upper)

    with pd.ExcelWriter(ruta_completa, engine="openpyxl") as writer:
        df_out.to_excel(writer, sheet_name=nombre_hoja, index=False)

    logger.info(
        "Archivo exportado: %s (%d filas, %d columnas)",
        ruta_completa, len(df_out), len(df_out.columns),
    )
    return {"ruta_archivo": ruta_completa, "filas": len(df_out)}
