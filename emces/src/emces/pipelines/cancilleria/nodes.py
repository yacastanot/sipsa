"""Nodos del pipeline de Cancillería EMCES.

Migración del script SAS Cancilleria-EMCES 2026-01.sas a Python/Kedro.
Proceso mensual: transforma gastos de funcionamiento de Cancillería
al formato de registro administrativo EMCES.

Correspondencia SAS → Python
────────────────────────────────────────────────────────────────────────────────
PROC IMPORT (DEVENGADOS, GASTOS)          → leer_devengados / leer_gastos
DATA BASE1 SET DEVENGADOS GASTOS          → construir_base1
PROC IMPORT (TRM) + DATA TRM/TRM_COL     → leer_trm_cancilleria
PROC TRANSPOSE → DATA TRM_2 → TRM_3      → filtrar_y_transformar_trm
PROC IMPORT (PAISES, PAISES1)             → leer_paises_cancilleria /
                                            leer_paises_acuerdos_cancilleria
DATA BASE2  MERGE BASE1 PAISES BY País   → enriquecer_con_paises
DATA BASE3  MERGE BASE2 TRM_3 BY PM/MON  → enriquecer_con_trm
DATA BASE4  cálculos monetarios          → calcular_campos_monetarios
PROC SQL GROUP BY                         → agregar_por_pais
DATA BASE6  MERGE BASE5 PAISES1 BY PAIS  → enriquecer_con_acuerdos
DATA BASE7  campos fijos EMCES           → construir_layout_emces
DATA BASE8  RETAIN (reorden columnas)    → (orden aplicado en construir_layout)
PROC EXPORT                              → exportar_excel
"""
from __future__ import annotations

import logging
import os

import pandas as pd

from emces.utils import (
    ORDEN_FINAL_RA as ORDEN_FINAL,
    alinear_a_schema_ra,
    leer_hoja_excel as _leer_hoja_excel,
    normalizar_col as _normalizar_col,
    normalizar_nombres as _normalizar_nombres,
    validar_columnas as _validar_columnas,
)

logger = logging.getLogger(__name__)


# Columnas que se deben dejar como espacio en blanco (no tienen valor en Cancillería)
_CAMPOS_VACIOS: list[str] = [
    "idact", "idtipodo", "idnitcc", "iddv",
    "razsoc", "nombre", "sigla", "direccion",
    "idmpio", "nom_mpio", "iddepto", "nom_depto",
    "telefono", "ext", "celular", "filial",
    "rep_legal", "celular_rep_legal", "telefono_rep_legal", "ext_rep_legal",
    "idmail_rep_legal", "idmail_rep_legalconf",
    "contacto", "cargo",
    "idtel2", "idtel3", "idtelext2", "idcel_2", "idcel_3",
    "idmail3", "idmail3conf", "idmail4", "idmail4conf",
    "observacion", "justificacion_critico", "justificacion_logistico",
    "justificacion_supervisor",
]


# ─── Nodos de ingesta ─────────────────────────────────────────────────────────

def leer_devengados(
    ruta_entrada: str,
    archivo_base: str,
    hoja: str,
) -> pd.DataFrame:
    """Lee la hoja Devengados_Neto del archivo base de Cancillería.

    Equivale a:
        PROC IMPORT SHEET=Devengados_Neto;
        DATA DEVENGADOS; SET DEVENGADOS; DESCRIPCION_CABPS='DEVENGADOS';

    Supuesto: la hoja tiene columnas 'Año', 'Mes', 'País', 'MONEDA', 'TOTAL'.
    """
    ruta = os.path.join(ruta_entrada, archivo_base)
    df = _leer_hoja_excel(ruta, hoja)
    df = _normalizar_nombres(df)
    df["descripcion_cabps"] = "DEVENGADOS"
    logger.info("raw_devengados: %d filas, columnas=%s", len(df), list(df.columns))
    return df


def leer_gastos(
    ruta_entrada: str,
    archivo_base: str,
    hoja: str,
) -> pd.DataFrame:
    """Lee la hoja Gastos_Funcionamiento del archivo base de Cancillería.

    Equivale a:
        PROC IMPORT SHEET=Gastos_Funcionamiento;
        DATA GASTOS; SET GASTOS; DESCRIPCION_CABPS='GASTOS';
    """
    ruta = os.path.join(ruta_entrada, archivo_base)
    df = _leer_hoja_excel(ruta, hoja)
    df = _normalizar_nombres(df)
    df["descripcion_cabps"] = "GASTOS"
    logger.info("raw_gastos: %d filas, columnas=%s", len(df), list(df.columns))
    return df


def leer_trm_cancilleria(
    ruta_entrada: str,
    archivo_parametricas: str,
    hoja: str,
) -> pd.DataFrame:
    """Lee la hoja Cancilleria_TRM de las paramétricas sin normalizar nombres.

    Los nombres de columna de moneda (PE, USD, EUR, etc.) se preservan
    para usarlos como valores de MONEDA después del PROC TRANSPOSE (melt).
    Solo se normaliza para identificar PERIODO y MES internamente.
    """
    ruta = os.path.join(ruta_entrada, archivo_parametricas)
    df = _leer_hoja_excel(ruta, hoja)
    logger.info("raw_trm: %d filas, columnas=%s", len(df), list(df.columns))
    return df


def leer_paises_cancilleria(
    ruta_entrada: str,
    archivo_parametricas: str,
    hoja: str,
) -> pd.DataFrame:
    """Lee la hoja Cancilleria_P de las paramétricas.

    Equivale a PROC IMPORT SHEET=Cancilleria_P.
    Columnas esperadas (antes de normalizar): 'País', 'NOMBRE PAÍS', 'CÓDIGO PAÍS'.
    """
    ruta = os.path.join(ruta_entrada, archivo_parametricas)
    df = _leer_hoja_excel(ruta, hoja)
    df = _normalizar_nombres(df)
    logger.info("raw_paises: %d filas, columnas=%s", len(df), list(df.columns))
    return df


def leer_paises_acuerdos_cancilleria(
    ruta_entrada: str,
    archivo_parametricas: str,
    hoja: str,
) -> pd.DataFrame:
    """Lee la hoja T_P_PAIS-ACUERDOS de las paramétricas.

    Equivale a PROC IMPORT SHEET='T_P_PAIS-ACUERDOS'.
    Columnas esperadas: PAIS, PAIS_COD_ISO_3166, PAIS_COD_ALPHA_3, ACUERDO_1/2/3.
    """
    ruta = os.path.join(ruta_entrada, archivo_parametricas)
    df = _leer_hoja_excel(ruta, hoja)
    df = _normalizar_nombres(df)
    logger.info("raw_paises1: %d filas, columnas=%s", len(df), list(df.columns))
    return df


# ─── Nodos de transformación ──────────────────────────────────────────────────

def construir_base1(
    df_devengados: pd.DataFrame,
    df_gastos: pd.DataFrame,
    periodo: str,
    mes: str,
) -> pd.DataFrame:
    """Concatena DEVENGADOS y GASTOS, construye PERIODO_MES y estandariza PERIODO.

    Equivale a:
        DATA BASE1;
        SET DEVENGADOS GASTOS;
        PERIODO_MES = COMPRESS(Año || '_' || Mes);
        RENAME Año = PERIODO;

    Supuesto: después de _normalizar_nombres, la columna de año se llama 'ano'
    (Año→NFD→strip tildes→ano) y la de país se llama 'pais'.
    Si los nombres difieren en el Excel, ajustar en parameters.yml.
    """
    cols_minimas = ["ano", "mes", "pais", "moneda", "total"]
    for df, nombre in [(df_devengados, "devengados"), (df_gastos, "gastos")]:
        _validar_columnas(df, cols_minimas, nombre)

    df = pd.concat([df_devengados, df_gastos], ignore_index=True)

    # PERIODO_MES con mes zero-padded para garantizar formato "YYYY_MM"
    df["ano"] = df["ano"].astype(str).str.strip()
    df["mes"] = df["mes"].astype(str).str.strip().str.zfill(2)
    df["periodo_mes"] = df["ano"] + "_" + df["mes"]

    # RENAME Año → PERIODO
    df = df.rename(columns={"ano": "periodo"})

    # Normalizar moneda a mayúsculas para el join con TRM
    df["moneda"] = df["moneda"].astype(str).str.strip().str.upper()

    logger.info(
        "base1: %d filas (devengados=%d, gastos=%d), periodo_mes ejemplo: %s",
        len(df), len(df_devengados), len(df_gastos),
        df["periodo_mes"].iloc[0] if not df.empty else "N/A",
    )
    return df


def filtrar_y_transformar_trm(
    df_trm_raw: pd.DataFrame,
    periodo: str,
    mes: str,
) -> pd.DataFrame:
    """Filtra la TRM para el periodo/mes objetivo y la convierte a formato largo.

    Equivale en SAS a:
        DATA TRM: filtra por PERIODO_MES = '2026_01'
        DATA TRM_COL: TRM_COL = 1/PE; KEEP PERIODO_MES TRM_COL
        PROC TRANSPOSE DATA=TRM OUT=TRM_1; BY PERIODO_MES
        DATA TRM_2: MONEDA=_LABEL_; TASA_DE_CAMBIO=COL1
        DATA TRM_3: MERGE TRM_COL TRM_2 BY PERIODO_MES

    En Python: pd.melt() reemplaza PROC TRANSPOSE.

    Supuesto: las columnas de moneda en el Excel son exactamente los códigos
    que aparecen en la columna MONEDA de DEVENGADOS/GASTOS (ej. 'USD', 'EUR', 'PE').
    La columna 'PE' contiene la tasa del peso colombiano.

    Supuesto TRM_COL: PE es la inversa de TRM_COL (TRM_COL = 1/PE).
    Si PE = valor en COP/unidad-USD, entonces TRM_COL convierte dólares a pesos.
    """
    df = df_trm_raw.copy()

    # Identificar columnas PERIODO y MES de forma robusta (case-insensitive)
    col_mapa = {_normalizar_col(c): c for c in df.columns}
    col_periodo_orig = col_mapa.get("periodo")
    col_mes_orig = col_mapa.get("mes")

    if col_periodo_orig is None or col_mes_orig is None:
        raise ValueError(
            f"TRM: no se encontraron columnas PERIODO o MES. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    # Construir PERIODO_MES desde los datos de la tabla
    df["_periodo_str"] = df[col_periodo_orig].astype(str).str.strip()
    df["_mes_str"] = df[col_mes_orig].astype(str).str.strip().str.zfill(2)
    df["periodo_mes"] = df["_periodo_str"] + "_" + df["_mes_str"]

    # Filtro equivalente a: IF PERIODO_MES = PERIODO_MES1
    periodo_mes_objetivo = f"{periodo}_{str(mes).zfill(2)}"
    df_filtrado = df[df["periodo_mes"] == periodo_mes_objetivo].copy()

    if df_filtrado.empty:
        disponibles = sorted(df["periodo_mes"].unique())
        raise ValueError(
            f"No hay datos de TRM para '{periodo_mes_objetivo}'. "
            f"Periodos disponibles: {disponibles}"
        )

    # Columnas de moneda = todas menos PERIODO, MES y derivadas temporales
    cols_excluir = {col_periodo_orig, col_mes_orig, "_periodo_str", "_mes_str"}
    cols_moneda = [c for c in df_filtrado.columns if c not in cols_excluir and c != "periodo_mes"]

    # Buscar PE (case-insensitive) para calcular TRM_COL = 1/PE
    col_pe = next(
        (c for c in cols_moneda if c.strip().upper() == "PE"),
        None,
    )
    if col_pe is None:
        raise ValueError(
            f"No se encontró columna 'PE' en TRM. Columnas de moneda: {cols_moneda}"
        )

    pe_valor = pd.to_numeric(df_filtrado[col_pe].iloc[0], errors="coerce")
    if pd.isna(pe_valor) or pe_valor == 0:
        raise ValueError(f"Valor PE inválido para {periodo_mes_objetivo}: {pe_valor!r}")

    trm_col = 1.0 / pe_valor

    # PROC TRANSPOSE: wide → long (una fila por moneda)
    # var_name captura el nombre de columna del Excel como valor de MONEDA
    df_largo = (
        df_filtrado[["periodo_mes"] + cols_moneda]
        .melt(id_vars=["periodo_mes"], var_name="moneda", value_name="tasa_de_cambio")
    )

    # Normalizar moneda a mayúsculas para coincidir con los valores en BASE1
    df_largo["moneda"] = df_largo["moneda"].str.strip().str.upper()
    df_largo["tasa_de_cambio"] = pd.to_numeric(df_largo["tasa_de_cambio"], errors="coerce")

    # Agregar TRM_COL (constante para el periodo, equivalente al MERGE TRM_COL TRM_2)
    df_largo["trm_col"] = trm_col

    # Eliminar filas sin tasa (monedas sin datos para este periodo)
    df_largo = df_largo.dropna(subset=["tasa_de_cambio"])

    logger.info(
        "trm_largo: periodo_mes=%s, %d monedas disponibles, TRM_COL=%.6f",
        periodo_mes_objetivo, len(df_largo), trm_col,
    )
    return df_largo


def enriquecer_con_paises(
    df_base1: pd.DataFrame,
    df_paises: pd.DataFrame,
) -> pd.DataFrame:
    """Une BASE1 con la tabla de países Cancilleria_P por la columna 'pais'.

    Equivale a:
        PROC SORT DATA=BASE1; BY País;
        PROC SORT DATA=PAISES; BY País;
        DATA BASE2; MERGE BASE1(IN=A) PAISES(IN=B); IF A; BY País;

    Supuesto: después de _normalizar_nombres, PAISES tiene columnas:
        'pais'        (de 'País'        — llave de join)
        'nombre_pais' (de 'NOMBRE PAÍS' — nombre para mostrar)
        'codigo_pais' (de 'CÓDIGO PAÍS' — código numérico del país)

    Filas de BASE1 sin correspondencia en PAISES se conservan (left join)
    con nombre_pais y codigo_pais = NaN, y se registra una advertencia.
    """
    _validar_columnas(df_paises, ["pais", "nombre_pais", "codigo_pais"], "paises")

    df = df_base1.copy()
    df_p = df_paises[["pais", "nombre_pais", "codigo_pais"]].copy()

    df["pais"] = df["pais"].astype(str).str.strip()
    df_p["pais"] = df_p["pais"].astype(str).str.strip()

    df_resultado = df.merge(df_p, on="pais", how="left")

    sin_match = df_resultado["nombre_pais"].isna().sum()
    if sin_match > 0:
        paises_sin_match = df_resultado[df_resultado["nombre_pais"].isna()]["pais"].unique()
        logger.warning(
            "base2: %d filas sin match en PAISES. Valores sin match: %s",
            sin_match, list(paises_sin_match),
        )

    logger.info("base2: %d filas tras join con PAISES (sin match: %d)", len(df_resultado), sin_match)
    return df_resultado


def enriquecer_con_trm(
    df_base2: pd.DataFrame,
    df_trm_largo: pd.DataFrame,
) -> pd.DataFrame:
    """Une BASE2 con TRM_3 por (periodo_mes, moneda).

    Equivale a:
        PROC SORT DATA=BASE2; BY PERIODO_MES MONEDA;
        PROC SORT DATA=TRM_3; BY PERIODO_MES MONEDA;
        DATA BASE3; MERGE BASE2(IN=A) TRM_3(IN=B); IF A; BY PERIODO_MES MONEDA;

    Filas sin tasa de cambio (moneda no encontrada en TRM) se conservan con
    tasa_de_cambio = NaN y quedan sujetas al filtro posterior de ceros.
    """
    df = df_base2.copy()
    df["moneda"] = df["moneda"].astype(str).str.strip().str.upper()
    df["periodo_mes"] = df["periodo_mes"].astype(str).str.strip()

    df_resultado = df.merge(df_trm_largo, on=["periodo_mes", "moneda"], how="left")

    sin_tasa = df_resultado["tasa_de_cambio"].isna().sum()
    if sin_tasa > 0:
        monedas_sin_tasa = df_resultado[df_resultado["tasa_de_cambio"].isna()]["moneda"].unique()
        logger.warning(
            "base3: %d filas sin tasa de cambio. Monedas no encontradas: %s",
            sin_tasa, list(monedas_sin_tasa),
        )

    logger.info("base3: %d filas tras join con TRM (sin tasa: %d)", len(df_resultado), sin_tasa)
    return df_resultado


def calcular_campos_monetarios(df_base3: pd.DataFrame) -> pd.DataFrame:
    """Calcula los campos monetarios y aplica renombres/filtros de BASE4.

    Equivale a:
        DATA BASE4;
        SET BASE3;
        TOTAL_EN_DOLARES = (TOTAL * TASA_DE_CAMBIO) / 1000;
        TOTAL_EN_MILES_DE_PESOS = TOTAL_EN_DOLARES * TRM_COL;
        TRM_BASE = 1 / TRM_COL;
        RENAME 'NOMBRE PAÍS'N = NOMBRE_PAIS;
        RENAME 'CÓDIGO PAÍS'N = PAIS;          ← codigo_pais → pais (numérico)
        IF TOTAL_EN_MILES_DE_PESOS = 0 THEN DELETE;
        IF TOTAL_EN_DOLARES = 0 THEN DELETE;

    Supuesto: TOTAL está en la moneda indicada por la columna MONEDA.
    La operación /1000 convierte a miles (asumiendo que TOTAL viene en unidades).
    """
    _validar_columnas(
        df_base3,
        ["total", "tasa_de_cambio", "trm_col", "nombre_pais", "codigo_pais"],
        "calcular_campos_monetarios",
    )

    df = df_base3.copy()
    df["total"] = pd.to_numeric(df["total"], errors="coerce")
    df["tasa_de_cambio"] = pd.to_numeric(df["tasa_de_cambio"], errors="coerce")
    df["trm_col"] = pd.to_numeric(df["trm_col"], errors="coerce")

    # Cálculos monetarios — réplica exacta de las fórmulas SAS
    df["total_en_dolares"] = (df["total"] * df["tasa_de_cambio"]) / 1000
    df["total_en_miles_de_pesos"] = df["total_en_dolares"] * df["trm_col"]
    df["trm_base"] = 1.0 / df["trm_col"]

    # RENAME 'CÓDIGO PAÍS'N = PAIS: el código numérico reemplaza la llave de texto
    # La columna original 'pais' (nombre de país del join) se descarta
    df = df.drop(columns=["pais"])
    df = df.rename(columns={"codigo_pais": "pais"})

    # Filtro: IF TOTAL_EN_MILES_DE_PESOS=0 THEN DELETE; IF TOTAL_EN_DOLARES=0 THEN DELETE
    antes = len(df)
    df = df[
        df["total_en_miles_de_pesos"].notna() & (df["total_en_miles_de_pesos"] != 0)
        & df["total_en_dolares"].notna() & (df["total_en_dolares"] != 0)
    ]
    eliminadas = antes - len(df)
    logger.info("base4: %d filas eliminadas por totales cero/nulos. Quedan %d", eliminadas, len(df))
    return df


def agregar_por_pais(df_base4: pd.DataFrame) -> pd.DataFrame:
    """Agrega los totales monetarios por país y fuente.

    Equivale a:
        PROC SQL;
        CREATE TABLE BASE5 AS
        SELECT PERIODO, MES, PERIODO_MES, PAIS, DESCRIPCION_CABPS,
               NOMBRE_PAIS, TRM_BASE,
               SUM(TOTAL_EN_DOLARES)        AS TOTAL_EN_DOLARES,
               SUM(TOTAL_EN_MILES_DE_PESOS) AS TOTAL_EN_MILES_DE_PESOS
        FROM BASE4
        GROUP BY PERIODO, MES, PERIODO_MES, PAIS, DESCRIPCION_CABPS,
                 NOMBRE_PAIS, TRM_BASE;
    """
    groupby_cols = [
        "periodo", "mes", "periodo_mes",
        "pais", "descripcion_cabps", "nombre_pais", "trm_base",
    ]
    _validar_columnas(
        df_base4,
        groupby_cols + ["total_en_dolares", "total_en_miles_de_pesos"],
        "agregar_por_pais",
    )

    df = (
        df_base4
        .groupby(groupby_cols, as_index=False, dropna=False)
        .agg(
            total_en_dolares=("total_en_dolares", "sum"),
            total_en_miles_de_pesos=("total_en_miles_de_pesos", "sum"),
        )
    )

    logger.info("base5 (agregada): %d filas tras GROUP BY por país", len(df))
    return df


def enriquecer_con_acuerdos(
    df_base5: pd.DataFrame,
    df_paises1: pd.DataFrame,
) -> pd.DataFrame:
    """Une BASE5 con PAISES1 (T_P_PAIS-ACUERDOS) por código de país.

    Equivale a:
        PROC SORT DATA=BASE5; BY PAIS;
        PROC SORT DATA=PAISES1; BY PAIS;
        DATA BASE6; MERGE BASE5(IN=A) PAISES1(IN=B); BY PAIS; IF A;

    Agrega columnas de clasificación internacional:
    PAIS_COD_ISO_3166, PAIS_COD_ALPHA_3, ACUERDO_1/2/3.
    """
    df = df_base5.copy()
    df_p1 = df_paises1.copy()

    # Llave numérica — alinear tipos antes del join
    df["pais"] = pd.to_numeric(df["pais"], errors="coerce")
    df_p1["pais"] = pd.to_numeric(df_p1["pais"], errors="coerce")

    # Seleccionar solo las columnas relevantes de PAISES1
    cols_acuerdos = [
        "pais", "pais_cod_iso_3166", "pais_cod_alpha_3",
        "acuerdo_1", "acuerdo_2", "acuerdo_3",
    ]
    cols_disponibles = [c for c in cols_acuerdos if c in df_p1.columns]
    df_p1 = df_p1[cols_disponibles]

    df_resultado = df.merge(df_p1, on="pais", how="left")

    if "pais_cod_iso_3166" in df_resultado.columns:
        df_resultado["pais_cod_iso_3166"] = pd.to_numeric(
            df_resultado["pais_cod_iso_3166"], errors="coerce"
        )

    sin_match = 0
    if "pais_cod_iso_3166" in df_resultado.columns:
        sin_match = df_resultado["pais_cod_iso_3166"].isna().sum()
    if sin_match > 0:
        paises_sin = df_resultado[df_resultado["pais_cod_iso_3166"].isna()]["pais"].unique()
        logger.warning(
            "base6: %d filas sin match en PAISES1 (acuerdos). Códigos: %s",
            sin_match, list(paises_sin),
        )

    logger.info("base6: %d filas tras join con PAISES1 (sin match: %d)", len(df_resultado), sin_match)
    return df_resultado


# ─── Nodos de reporting ───────────────────────────────────────────────────────

def construir_layout_emces(
    df_base6: pd.DataFrame,
    periodo: str,
    mes: str,
    mes_nombre: str,
) -> pd.DataFrame:
    """Agrega los campos fijos del formato EMCES y reordena las columnas.

    Equivale a:
        DATA BASE7: asignaciones de campos fijos del layout EMCES
        DATA BASE8: RETAIN (reorden de columnas)

    Los valores fijos son específicos de Cancillería:
        - FLUJO_COMERCIAL = 'IMPORTACIONES GASTOS DEL GOBIERNO'
        - MODO = 2 (consumidor en el exterior)
        - Agrupacion = 9, codigo = 291, cpc = '91119'
        - idnoremp = '999-1', departamento = 11 (Bogotá D.C.)
    """
    df = df_base6.copy()

    # ── Campos fijos del registro EMCES ───────────────────────────────────────
    df["flujo_comercial"] = "IMPORTACIONES GASTOS DEL GOBIERNO"
    df["idnoremp"] = "999-1"
    df["sede"] = "NA"
    df["csede"] = 0
    df["agrupacion"] = 9
    df["descripcion_grupo"] = "Importaciones Gastos Del Gobierno"
    df["codigo"] = 291
    df["cpc"] = "91119"
    # Nota: el SAS tiene 'sevicios' (typo). Se corrige aquí.
    df["descripcion_cpc"] = "Otros servicios de la administración pública n.c.p"
    df["nombre_departamento"] = "BOGOTA, D.C."
    df["departamento"] = 11
    df["vrocefats"] = 0
    df["vroce"] = 0
    df["construccion"] = 0
    df["total_vrocefats_dolares"] = 0
    df["total_vroce_dolares"] = 0
    df["total_construccion_dolares"] = 0
    df["modo"] = 2
    df["descripcion_modo"] = (
        "El consumidor consume el servicio fuera del territorio de su país."
    )
    df["id"] = "NA"
    df["nom_estado"] = "NA"
    df["novedad"] = 99
    df["ociser"] = 1

    # ── Campos de texto vacíos ────────────────────────────────────────────────
    for campo in _CAMPOS_VACIOS:
        if campo not in df.columns:
            df[campo] = " "

    # ── Convertir NaN en columnas de texto a cadena vacía ─────────────────────
    obj_cols = df.select_dtypes(include="object").columns
    df[obj_cols] = df[obj_cols].fillna("")

    # ── Proyectar al schema RA canónico (agrega cols faltantes, descarta extras) ─
    df = alinear_a_schema_ra(df, fuente="cancilleria")

    if df.empty:
        raise ValueError(
            f"El resultado final de Cancillería está vacío para {periodo}_{mes}. "
            "Revise los merges y los filtros de ceros."
        )

    logger.info("canc_maestro: %d filas finales para %s_%s", len(df), periodo, mes)
    return df


def exportar_excel(
    df_maestro: pd.DataFrame,
    ruta_salida: str,
    periodo: str,
    mes: str,
) -> dict[str, object]:
    """Exporta el resultado final a Excel con nombre dinámico.

    Equivale a:
        PROC EXPORT DATA=BASE8
        OUTFILE='...Cancillería_&PERIODO._&MES..xlsx'
        SHEET='Cancillería_&PERIODO._&MES.';

    Retorna un dict con metadata de la exportación (para trazabilidad).
    """
    nombre_hoja = f"Cancilleria_{periodo}_{mes}"
    nombre_archivo = f"Cancilleria_{periodo}_{mes}.xlsx"
    ruta_completa = os.path.join(ruta_salida, nombre_archivo)

    os.makedirs(ruta_salida, exist_ok=True)
    df_maestro.to_excel(ruta_completa, sheet_name=nombre_hoja, index=False, engine="openpyxl")

    logger.info("Exportado: %s (%d filas, hoja='%s')", ruta_completa, len(df_maestro), nombre_hoja)

    return {
        "ruta": ruta_completa,
        "filas": len(df_maestro),
        "hoja": nombre_hoja,
        "periodo": periodo,
        "mes": mes,
    }
