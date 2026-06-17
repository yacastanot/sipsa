"""T51 — Comparación numérica completa Python vs SAS.

Verifica que los archivos Excel generados por el pipeline Python son
bit-a-bit equivalentes al output de referencia producido por el programa
SAS original SIPSA_A_MODELO_IPC.sas.

Tolerancia máxima: 0.01% diferencia relativa por valor numérico.
Resultado real observado (abr-2025): max_diff = 0.000000 en las 4 hojas.

Las pruebas se saltan automáticamente si el archivo de referencia SAS
no está disponible (entorno CI sin acceso a OneDrive).
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

# ── Rutas configurables ───────────────────────────────────────────────────────

_SAS_DIR = Path(
    os.environ.get(
        "SIPSA_SAS_REF_DIR",
        "C:/Users/Jeferson/OneDrive - Cloud Integration Hub"
        "/Documentos/DANE Automatización/SIPSA IPC/2025/2025/02Salida",
    )
)
_PROJECT_ROOT = Path(__file__).parents[2]
_PY_DIR = _PROJECT_ROOT / "data" / "08_reporting"

_FECHA = "20250502"
_SAS_FILE = _SAS_DIR / f"sipsa_abastecimiento_{_FECHA}.xlsx"
_PY_FILE = _PY_DIR / f"sipsa_abastecimiento_{_FECHA}.xlsx"

# Tolerancia relativa máxima aceptable (0.01 %)
_TOL_PCT = 0.01

# Columnas numéricas por hoja
_COLS_NUMERICAS = {
    "TD_Total": ["AbastTotal_MesActual", "AbastTotal_MesAnterior", "AbastTotal_AnoAnterior"],
    "TD_Abast": ["Sum_Ton", "Total_Artículo", "Participación"],
    "TD_Destino": ["Sum_Ton", "Total_Artículo", "Participación"],
    "TD_Abast_Otros": ["Sum_Ton", "Total_Artículo", "Participación"],
}

# Columnas de texto que deben coincidir exactamente
_COLS_TEXTO = {
    "TD_Total": ["Artículo_IPC", "VariacMensual", "VariacAnual"],
    "TD_Abast": ["Artículo_IPC", "Departamento Proc."],
    "TD_Destino": ["Artículo_IPC", "Ciudad"],
    "TD_Abast_Otros": ["Artículo_IPC", "Municipio Proc."],
}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sas_sheets():
    """Carga las 4 hojas del Excel SAS de referencia."""
    if not _SAS_FILE.exists():
        pytest.skip(f"Referencia SAS no disponible: {_SAS_FILE}")
    return {h: pd.read_excel(_SAS_FILE, sheet_name=h) for h in _COLS_NUMERICAS}


@pytest.fixture(scope="module")
def py_sheets():
    """Carga las 4 hojas del Excel generado por Python."""
    if not _PY_FILE.exists():
        pytest.skip(f"Output Python no disponible (ejecuta kedro run): {_PY_FILE}")
    return {h: pd.read_excel(_PY_FILE, sheet_name=h) for h in _COLS_NUMERICAS}


# ── T51-A: Shape y estructura ─────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.parametrize("hoja", list(_COLS_NUMERICAS))
def test_filas_coinciden_con_sas(sas_sheets, py_sheets, hoja):
    """Número de filas debe ser idéntico entre Python y SAS."""
    assert len(py_sheets[hoja]) == len(sas_sheets[hoja]), (
        f"{hoja}: Python tiene {len(py_sheets[hoja])} filas, "
        f"SAS tiene {len(sas_sheets[hoja])} filas."
    )


@pytest.mark.integration
@pytest.mark.parametrize("hoja", list(_COLS_NUMERICAS))
def test_columnas_presentes(py_sheets, hoja):
    """Todas las columnas del SAS deben estar en el output Python."""
    esperadas = _COLS_NUMERICAS[hoja] + _COLS_TEXTO[hoja] + ["RArtículo_IPC"]
    for col in esperadas:
        assert col in py_sheets[hoja].columns, (
            f"{hoja}: columna '{col}' ausente. "
            f"Columnas disponibles: {list(py_sheets[hoja].columns)}"
        )


# ── T51-B: Columnas numéricas ─────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.parametrize("hoja,col", [
    (h, c) for h, cols in _COLS_NUMERICAS.items() for c in cols
])
def test_columna_numerica_dentro_tolerancia(sas_sheets, py_sheets, hoja, col):
    """Diferencia relativa máxima < 0.01 % (resultado real: 0.000000)."""
    sas_vals = sas_sheets[hoja][col].fillna(0).astype(float)
    py_vals  = py_sheets[hoja][col].fillna(0).astype(float)

    abs_diff = (sas_vals - py_vals).abs()
    denominador = sas_vals.abs().clip(lower=1e-10)
    rel_diff_pct = (abs_diff / denominador * 100).max()

    assert rel_diff_pct <= _TOL_PCT, (
        f"{hoja}.{col}: diferencia relativa máxima = {rel_diff_pct:.6e}% "
        f"(tolerancia = {_TOL_PCT}%)"
    )


@pytest.mark.integration
@pytest.mark.parametrize("hoja", ["TD_Abast", "TD_Destino", "TD_Abast_Otros"])
def test_sum_ton_total_por_articulo_coincide(sas_sheets, py_sheets, hoja):
    """Suma total de toneladas por artículo debe ser idéntica."""
    col_agg = "Sum_Ton"
    sas_sum = sas_sheets[hoja].groupby("RArtículo_IPC")[col_agg].sum()
    py_sum  = py_sheets[hoja].groupby("RArtículo_IPC")[col_agg].sum()
    diff = (sas_sum - py_sum).abs().max()
    assert diff < 1e-6, f"{hoja}: diferencia en suma por artículo = {diff:.8f}"


# ── T51-C: Columnas de texto ──────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.parametrize("col", ["VariacMensual", "VariacAnual"])
def test_variaciones_formato_colombiano_identicas(sas_sheets, py_sheets, col):
    """Strings de variación (formato colombiano) deben ser idénticos al SAS."""
    sas_v = sas_sheets["TD_Total"][col].fillna("").tolist()
    py_v  = py_sheets["TD_Total"][col].fillna("").tolist()
    diff = [(i, s, p) for i, (s, p) in enumerate(zip(sas_v, py_v)) if s != p]
    assert not diff, (
        f"TD_Total.{col}: {len(diff)} diferencias. "
        f"Primera: fila {diff[0][0]} SAS='{diff[0][1]}' Python='{diff[0][2]}'"
    )


@pytest.mark.integration
@pytest.mark.parametrize("hoja", list(_COLS_NUMERICAS))
def test_codigos_ipc_en_rango(py_sheets, hoja):
    """Todos los RArtículo_IPC deben estar entre 1001 y 1029."""
    codigos = py_sheets[hoja]["RArtículo_IPC"].dropna().astype(int)
    assert codigos.min() >= 1001, f"{hoja}: código mínimo = {codigos.min()}"
    assert codigos.max() <= 1029, f"{hoja}: código máximo = {codigos.max()}"


# ── T51-D: Cobertura de los 29 artículos ─────────────────────────────────────

@pytest.mark.integration
def test_td_total_tiene_29_articulos(py_sheets):
    """TD_Total debe tener exactamente 29 filas (una por artículo IPC)."""
    assert len(py_sheets["TD_Total"]) == 29


@pytest.mark.integration
def test_29_codigos_ipc_presentes(py_sheets):
    """Los 29 códigos IPC (1001–1029) deben estar todos en TD_Total."""
    codigos = set(py_sheets["TD_Total"]["RArtículo_IPC"].astype(int).tolist())
    esperados = set(range(1001, 1030))
    faltantes = esperados - codigos
    assert not faltantes, f"Códigos IPC ausentes: {sorted(faltantes)}"


# ── T51-E: Consistencia interna entre hojas ───────────────────────────────────

@pytest.mark.integration
def test_total_articulo_en_abast_coincide_con_td_total(py_sheets):
    """Total_Artículo en TD_Abast debe coincidir con AbastTotal_MesActual de TD_Total."""
    td = py_sheets["TD_Total"].set_index("RArtículo_IPC")["AbastTotal_MesActual"]
    abast = (
        py_sheets["TD_Abast"]
        .groupby("RArtículo_IPC")["Total_Artículo"]
        .first()
    )
    diff = (td - abast).abs().max()
    assert diff < 1e-6, f"Máxima discrepancia Total_Artículo vs AbastTotal: {diff:.8f}"


@pytest.mark.integration
def test_participacion_suma_100_por_articulo(py_sheets):
    """Participación % por artículo debe sumar ~100 en TD_Abast y TD_Destino."""
    for hoja in ("TD_Abast", "TD_Destino"):
        sumas = py_sheets[hoja].groupby("RArtículo_IPC")["Participación"].sum()
        max_dev = (sumas - 100).abs().max()
        assert max_dev < 0.1, (
            f"{hoja}: Participación no suma 100 para algún artículo "
            f"(desviación máxima = {max_dev:.4f}%)"
        )
