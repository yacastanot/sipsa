"""Nodos del pipeline de preparación mensual — FASE 0.

Valida el archivo de entrada y construye la configuración IPC para el mes:

  [1/4]  Los tres períodos (t, t-1, t-12) están presentes en BASE SIPSA_A.
          Si alguno falta, el pipeline se detiene con error antes de procesar.

  [3/4]  La lista de artículos en Artículos_IPC coincide con la de
          Alimentos IPC Vs SIPSA_A. Las diferencias se reportan como advertencias.

  [4/4]  Se asignan códigos 1001, 1002, ... en orden alfabético a los artículos
          seleccionados este mes. Se construye el mapeo variedades SIPSA → artículo IPC
          directamente desde las cols 4-5 de Alimentos IPC Vs SIPSA_A. Los códigos
          NO se persisten en YAML: se recalculan fresh cada mes.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

_HOJA_BASE      = "BASE SIPSA_A"
_HOJA_ALIMENTOS = "Alimentos IPC Vs SIPSA_A"

# Encabezados de columna en la hoja de priorizados que NO son variedades.
_CABECERAS_HOJA = {"IPC", "SIPSA"}

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def preparar_articulos_ipc(
    archivo_entrada: str,
    mes_actual_nombre: str,
    mes_anterior_nombre: str,
    anio_actual: int,
    anio_anterior: int,
    articulos_ipc: dict[str, Any],
) -> dict[str, Any]:
    """Valida el archivo de entrada y retorna la configuración IPC del mes.

    Args:
        archivo_entrada: Ruta relativa al archivo Excel de entrada mensual.
        mes_actual_nombre: Nombre en español del mes actual (ej. ``"Mayo"``).
        mes_anterior_nombre: Nombre del mes anterior (ej. ``"Abril"``).
        anio_actual: Año del período actual.
        anio_anterior: Año para el comparativo anual (t-12).
        articulos_ipc: Configuración leída de ``parameters_articulos_ipc.yml``
            (contiene la clave ``correlativa`` con la tabla maestra completa).

    Returns:
        Diccionario ``{"variedades": {...}, "codigos": {...}}`` con los
        artículos y códigos calculados para este mes específicamente.
        Los códigos se asignan 1001, 1002, ... en orden alfabético.

    Raises:
        FileNotFoundError: Si el archivo de entrada no existe.
        ValueError: Si alguno de los tres períodos no se encuentra en el archivo.
    """
    ruta = _resolver_ruta(archivo_entrada)
    correlativa = articulos_ipc.get("correlativa", {})

    _validar_periodos(ruta, mes_actual_nombre, mes_anterior_nombre, anio_actual, anio_anterior)
    _verificar_consistencia(ruta)
    config_mes = _construir_config_mensual(ruta, correlativa)

    return config_mes


# ─── [1/4] Validación de períodos ─────────────────────────────────────────────

def _validar_periodos(
    ruta: Path,
    mes_actual_nombre: str,
    mes_anterior_nombre: str,
    anio_actual: int,
    anio_anterior: int,
) -> None:
    """Verifica que t, t-1 y t-12 estén en FechaEncuesta. Lanza ValueError si falta alguno."""
    num_actual   = MESES_ES.get(mes_actual_nombre.strip().lower())
    num_anterior = MESES_ES.get(mes_anterior_nombre.strip().lower())

    if not num_actual or not num_anterior:
        raise ValueError(
            f"Nombre de mes no reconocido: '{mes_actual_nombre}' / '{mes_anterior_nombre}'. "
            "Revisa parameters.yml."
        )

    periodo_t   = (anio_actual,   num_actual)
    periodo_tm1 = (anio_actual - 1, 12) if num_actual == 1 else (anio_actual, num_anterior)
    periodo_t12 = (anio_anterior, num_actual)

    log.info(
        "preparar_articulos_ipc | leyendo FechaEncuesta de '%s' para validar períodos ...",
        ruta.name,
    )
    df = pd.read_excel(str(ruta), sheet_name=_HOJA_BASE,
                       usecols=["FechaEncuesta"], parse_dates=["FechaEncuesta"])

    errores: list[str] = []
    for (anio, mes), etiqueta in [
        (periodo_t,   f"t    ({mes_actual_nombre} {anio_actual})"),
        (periodo_tm1, f"t-1  ({mes_anterior_nombre} {periodo_tm1[0]})"),
        (periodo_t12, f"t-12 ({mes_actual_nombre} {anio_anterior})"),
    ]:
        n = int((df["FechaEncuesta"].dt.year.eq(anio) & df["FechaEncuesta"].dt.month.eq(mes)).sum())
        if n == 0:
            errores.append(f"Período {etiqueta} no encontrado en FechaEncuesta.")
            log.error("preparar_articulos_ipc | [1/4] [ERR] %s: 0 filas", etiqueta)
        else:
            log.info("preparar_articulos_ipc | [1/4] [OK]  %s: %d filas", etiqueta, n)

    if errores:
        raise ValueError(
            "El archivo de entrada no contiene todos los períodos requeridos:\n"
            + "\n".join(f"  - {e}" for e in errores)
        )


# ─── [3/4] Verificación de consistencia ───────────────────────────────────────

def _verificar_consistencia(ruta: Path) -> None:
    """Compara la lista de artículos en Artículos_IPC vs Alimentos IPC Vs SIPSA_A."""
    try:
        xl = pd.ExcelFile(str(ruta))
    except Exception as exc:
        log.warning("preparar_articulos_ipc | [3/4] No se pudo abrir el archivo: %s", exc)
        return

    hoja_fmt = next(
        (s for s in xl.sheet_names if s.lower().startswith("art") and "ipc" in s.lower()),
        None,
    )
    if hoja_fmt is None:
        log.warning("preparar_articulos_ipc | [3/4] Hoja Artículos_IPC no encontrada; omitiendo.")
        return

    df_fmt = xl.parse(hoja_fmt, header=None)
    arts_formato = {
        v.strip().upper()
        for v in df_fmt.iloc[2:, 2].dropna().astype(str).tolist()
        if v.strip().upper() not in _CABECERAS_HOJA
    }

    if _HOJA_ALIMENTOS not in xl.sheet_names:
        log.warning(
            "preparar_articulos_ipc | [3/4] Hoja '%s' no encontrada.", _HOJA_ALIMENTOS
        )
        return

    df_prio = xl.parse(_HOJA_ALIMENTOS, header=None)
    arts_prio = {
        v.strip().upper()
        for v in df_prio.iloc[2:, 2].dropna().astype(str).tolist()
        if v.strip().upper() not in _CABECERAS_HOJA
    }

    log.info(
        "preparar_articulos_ipc | [3/4] Artículos_IPC=%d | Alimentos IPC Vs SIPSA_A=%d",
        len(arts_formato),
        len(arts_prio),
    )

    solo_fmt  = arts_formato - arts_prio
    solo_prio = arts_prio - arts_formato

    if not solo_fmt and not solo_prio:
        log.info("preparar_articulos_ipc | [3/4] [OK] Listas idénticas.")
    if solo_fmt:
        log.warning(
            "preparar_articulos_ipc | [3/4] [WARN] En Artículos_IPC pero NO en priorizados: %s",
            ", ".join(sorted(solo_fmt)),
        )
    if solo_prio:
        log.warning(
            "preparar_articulos_ipc | [3/4] [WARN] En priorizados pero NO en Artículos_IPC: %s",
            ", ".join(sorted(solo_prio)),
        )


# ─── [4/4] Construcción de configuración mensual ──────────────────────────────

def _construir_config_mensual(
    ruta: Path,
    correlativa: dict[str, list[str]],
) -> dict[str, Any]:
    """Asigna códigos y construye el mapeo de variedades para este mes.

    Los códigos se asignan 1001, 1002, ... en orden alfabético a los artículos
    seleccionados este mes (los de la col 2 de Alimentos IPC Vs SIPSA_A).
    Las variedades se leen directamente de las cols 4-5 de la misma hoja.
    """
    articulos_mes, mapping_mes = _leer_hoja_priorizados(ruta)

    if not articulos_mes:
        raise ValueError(
            "No se encontraron artículos IPC en la hoja 'Alimentos IPC Vs SIPSA_A'. "
            "Revisa el archivo de entrada."
        )

    # Asignar códigos 1001, 1002, ... en orden alfabético
    codigos: dict[str, int] = {
        art: 1001 + i
        for i, art in enumerate(sorted(articulos_mes))
    }

    log.info(
        "preparar_articulos_ipc | [4/4] %d articulos seleccionados este mes, "
        "codigos %d-%d",
        len(codigos), 1001, 1000 + len(codigos),
    )

    for art, cod in sorted(codigos.items(), key=lambda x: x[1]):
        log.info("preparar_articulos_ipc | [4/4]  %d -> %s", cod, art)

    # Construir variedades desde el mapeo mensual (cols 4-5 del Excel)
    variedades: dict[str, str] = {}
    for sipsa, ipc in mapping_mes:
        if ipc not in codigos:
            log.warning(
                "preparar_articulos_ipc | [4/4] Variedad '%s' mapeada a '%s' "
                "que NO está en la lista de artículos seleccionados; ignorando.",
                sipsa, ipc,
            )
            continue
        if sipsa in variedades and variedades[sipsa] != ipc:
            log.warning(
                "preparar_articulos_ipc | [4/4] Variedad '%s' mapeada a '%s' y '%s'; "
                "se usa la primera asignación.",
                sipsa, variedades[sipsa], ipc,
            )
            continue
        variedades[sipsa] = ipc

    log.info(
        "preparar_articulos_ipc | [4/4] %d variedades SIPSA mapeadas.",
        len(variedades),
    )

    # Validar contra la correlativa (aviso si hay variedades no registradas)
    correlativa_sipsa_cf = {
        sipsa.casefold()
        for variedades_ipc in correlativa.values()
        for sipsa in variedades_ipc
    }
    fuera_correlativa = [s for s in variedades if s.casefold() not in correlativa_sipsa_cf]
    if fuera_correlativa:
        log.warning(
            "preparar_articulos_ipc | [4/4] Variedades del mes NO registradas en "
            "la correlativa (parameters_articulos_ipc.yml): %s",
            ", ".join(sorted(fuera_correlativa)),
        )

    return {"variedades": variedades, "codigos": codigos}


def _leer_hoja_priorizados(ruta: Path) -> tuple[list[str], list[tuple[str, str]]]:
    """Lee artículos del mes (col 2) y mapping SIPSA→IPC (cols 4-5) de Alimentos IPC Vs SIPSA_A."""
    df = pd.read_excel(str(ruta), sheet_name=_HOJA_ALIMENTOS, header=None)
    inicio = 2  # fila 0 vacía, fila 1 = encabezados

    articulos_mes = [
        v for v in (
            df.iloc[inicio:, 2].dropna().str.strip().str.upper().tolist()
        )
        if v not in _CABECERAS_HOJA
    ]

    mapping_df = df.iloc[inicio:, [4, 5]].copy()
    mapping_df.columns = ["ipc", "sipsa"]
    mapping_df = mapping_df.dropna(subset=["sipsa"])
    mapping_df["ipc"] = mapping_df["ipc"].ffill()
    mapping_df = mapping_df.dropna(subset=["ipc"])

    mapping_mes = [
        (str(r["sipsa"]).strip(), str(r["ipc"]).strip().upper())
        for _, r in mapping_df.iterrows()
        if str(r["sipsa"]).strip()
        and str(r["ipc"]).strip()
        and str(r["sipsa"]).strip().upper() not in _CABECERAS_HOJA
        and str(r["ipc"]).strip().upper() not in _CABECERAS_HOJA
    ]
    return articulos_mes, mapping_mes


def _resolver_ruta(archivo_entrada: str) -> Path:
    """Resuelve la ruta del archivo de entrada."""
    ruta = Path(archivo_entrada)
    if not ruta.is_absolute():
        ruta = Path.cwd() / ruta
    if not ruta.exists():
        raise FileNotFoundError(
            f"Archivo de entrada no encontrado: '{archivo_entrada}'. "
            "Revisa 'archivo_entrada' en conf/base/parameters.yml."
        )
    return ruta
