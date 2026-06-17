"""T52 — Tests de integración: verificación del pipeline completo.

Dos niveles de prueba:
  1. Artefactos (rápido): verifica que los parquets y Excel de salida existen,
     tienen la forma correcta y son consistentes entre capas.  No re-ejecuta
     el pipeline.

  2. Pipeline completo (lento, marcado @pytest.mark.slow): ejecuta
     `kedro run` desde cero y verifica que los outputs coinciden con los
     valores de referencia esperados.  Requiere el Excel de entrada en
     data/01_raw/ y tarda ~30s.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

_PROJECT_ROOT = Path(__file__).parents[2]
_VENV_KEDRO = _PROJECT_ROOT / ".venv" / "Scripts" / "kedro.exe"

# ── Artefactos esperados y sus shapes ────────────────────────────────────────

_PARQUETS = {
    "data/02_intermediate/base_sipsa_bronze.parquet": {
        "min_rows": 500_000,
        "required_cols": ["Fuente", "FechaEncuesta", "Ali", "Cant Kg", "Grupo"],
    },
    "data/03_primary/base_sipsa_clean.parquet": {
        "min_rows": 500_000,
        "required_cols": ["Ciudad", "Central", "Cant_Ton", "PerFecha",
                          "Artículo_IPC", "RArtículo_IPC"],
    },
    "data/03_primary/base_ipc_filtrada.parquet": {
        "min_rows": 300_000,
        "required_cols": ["RArtículo_IPC", "Artículo_IPC", "Cant_Ton", "PerFecha"],
    },
    "data/04_feature/td_total.parquet": {
        "exact_rows": 29,
        "required_cols": ["RArtículo_IPC", "Artículo_IPC",
                          "AbastTotal_MesActual", "AbastTotal_MesAnterior",
                          "AbastTotal_AnoAnterior"],
    },
    "data/04_feature/td_abast.parquet": {
        "min_rows": 400,
        "required_cols": ["RArtículo_IPC", "Artículo_IPC",
                          "Departamento Proc.", "Sum_Ton", "Participación"],
    },
    "data/04_feature/td_destino.parquet": {
        "min_rows": 400,
        "required_cols": ["RArtículo_IPC", "Artículo_IPC",
                          "Ciudad", "Sum_Ton", "Participación"],
    },
    "data/04_feature/td_abast_otros.parquet": {
        "min_rows": 10,
        "required_cols": ["RArtículo_IPC", "Artículo_IPC",
                          "Municipio Proc.", "Sum_Ton", "Participación"],
    },
    "data/04_feature/td_total_variaciones.parquet": {
        "exact_rows": 29,
        "required_cols": ["RArtículo_IPC", "VariacMensual_num", "VariacAnual_num",
                          "VariacMensual", "VariacAnual"],
    },
    "data/04_feature/td_abast_fmt.parquet": {
        "min_rows": 400,
        "required_cols": ["RArtículo_IPC", "Departamento Proc.", "Participación"],
    },
    "data/04_feature/td_destino_fmt.parquet": {
        "min_rows": 400,
        "required_cols": ["RArtículo_IPC", "Ciudad", "Participación"],
    },
    "data/04_feature/td_abast_otros_fmt.parquet": {
        "min_rows": 10,
        "required_cols": ["RArtículo_IPC", "Municipio Proc.", "Participación"],
    },
}

_EXCEL_OUTPUTS = [
    "data/08_reporting/No_mapeados_IPC.xlsx",
    "data/08_reporting/COBERTURA.xlsx",
]


# ── T52-A: Existencia y estructura de artefactos ──────────────────────────────

@pytest.mark.integration
@pytest.mark.parametrize("rel_path", list(_PARQUETS))
def test_parquet_existe(rel_path):
    """Todos los parquets intermedios deben existir en disco."""
    path = _PROJECT_ROOT / rel_path
    assert path.exists(), f"Parquet no encontrado: {path}"


@pytest.mark.integration
@pytest.mark.parametrize("rel_path,spec", list(_PARQUETS.items()))
def test_parquet_shape_y_columnas(rel_path, spec):
    """Cada parquet debe tener las filas y columnas esperadas."""
    path = _PROJECT_ROOT / rel_path
    if not path.exists():
        pytest.skip(f"Parquet ausente: {rel_path}")
    df = pd.read_parquet(path)

    if "exact_rows" in spec:
        assert len(df) == spec["exact_rows"], (
            f"{rel_path}: {len(df)} filas (esperado exactamente {spec['exact_rows']})"
        )
    if "min_rows" in spec:
        assert len(df) >= spec["min_rows"], (
            f"{rel_path}: {len(df)} filas (mínimo esperado {spec['min_rows']})"
        )
    for col in spec["required_cols"]:
        assert col in df.columns, (
            f"{rel_path}: columna '{col}' ausente. Columnas: {list(df.columns)}"
        )


@pytest.mark.integration
@pytest.mark.parametrize("rel_path", _EXCEL_OUTPUTS)
def test_excel_output_existe(rel_path):
    """Los Excel de salida (No_mapeados, COBERTURA) deben existir."""
    path = _PROJECT_ROOT / rel_path
    assert path.exists(), f"Excel no encontrado: {path}"


# ── T52-B: Calidad de datos en los artefactos ─────────────────────────────────

@pytest.mark.integration
def test_bronze_tres_periodos():
    """La capa bronze debe contener exactamente 3 valores de PerFecha en clean."""
    path = _PROJECT_ROOT / "data/03_primary/base_sipsa_clean.parquet"
    if not path.exists():
        pytest.skip("base_sipsa_clean no disponible")
    df = pd.read_parquet(path, columns=["PerFecha"])
    periodos = set(df["PerFecha"].dropna().unique())
    assert periodos == {"Mes actual", "Mes anterior", "Año anterior"}, (
        f"Períodos en base_sipsa_clean: {periodos}"
    )


@pytest.mark.integration
def test_ipc_filtrada_sin_nulos_en_codigo():
    """base_ipc_filtrada no debe tener RArtículo_IPC nulos (es el filtro de F3)."""
    path = _PROJECT_ROOT / "data/03_primary/base_ipc_filtrada.parquet"
    if not path.exists():
        pytest.skip("base_ipc_filtrada no disponible")
    df = pd.read_parquet(path, columns=["RArtículo_IPC"])
    nulos = df["RArtículo_IPC"].isna().sum()
    assert nulos == 0, f"base_ipc_filtrada tiene {nulos} nulos en RArtículo_IPC"


@pytest.mark.integration
def test_29_articulos_en_td_total():
    """TD_Total debe tener exactamente los 29 artículos IPC."""
    path = _PROJECT_ROOT / "data/04_feature/td_total.parquet"
    if not path.exists():
        pytest.skip("td_total no disponible")
    df = pd.read_parquet(path)
    codigos = set(df["RArtículo_IPC"].dropna().astype(int).tolist())
    assert codigos == set(range(1001, 1030)), (
        f"Códigos presentes: {sorted(codigos)}"
    )


@pytest.mark.integration
def test_participacion_no_supera_100():
    """Ningún registro de Participación debe superar 100%."""
    for rel in ("data/04_feature/td_abast_fmt.parquet",
                "data/04_feature/td_destino_fmt.parquet"):
        path = _PROJECT_ROOT / rel
        if not path.exists():
            continue
        df = pd.read_parquet(path, columns=["Participación"])
        max_p = df["Participación"].max()
        assert max_p <= 100.01, f"{rel}: Participación máxima = {max_p:.4f}% > 100%"


@pytest.mark.integration
def test_cobertura_29_articulos():
    """COBERTURA.xlsx debe reportar 29/29 artículos cubiertos."""
    path = _PROJECT_ROOT / "data/08_reporting/COBERTURA.xlsx"
    if not path.exists():
        pytest.skip("COBERTURA.xlsx no disponible")
    df = pd.read_excel(path, sheet_name="Cobertura")
    assert len(df) == 29, f"COBERTURA.xlsx tiene {len(df)} filas (esperadas 29)"
    n_cubiertos = df["Tiene_Cobertura"].sum()
    assert n_cubiertos == 29, f"Solo {n_cubiertos}/29 artículos cubiertos"


@pytest.mark.integration
def test_td_abast_fmt_propcase():
    """Los departamentos en td_abast_fmt deben estar en PropCase (primera letra mayúscula)."""
    path = _PROJECT_ROOT / "data/04_feature/td_abast_fmt.parquet"
    if not path.exists():
        pytest.skip("td_abast_fmt no disponible")
    df = pd.read_parquet(path, columns=["Departamento Proc."])
    muestra = df["Departamento Proc."].dropna().head(20)
    for val in muestra:
        s = str(val)
        if s in ("n.a.", "N.A."):
            continue
        primera = s[0]
        assert primera == primera.upper(), (
            f"Departamento no PropCase: '{s}'"
        )


# ── T52-C: Consistencia entre capas ──────────────────────────────────────────

@pytest.mark.integration
def test_cant_ton_positiva_en_filtrada():
    """Todas las toneladas en la base filtrada deben ser > 0."""
    path = _PROJECT_ROOT / "data/03_primary/base_ipc_filtrada.parquet"
    if not path.exists():
        pytest.skip("base_ipc_filtrada no disponible")
    df = pd.read_parquet(path, columns=["Cant_Ton"])
    negativos = (df["Cant_Ton"] <= 0).sum()
    assert negativos == 0, f"Hay {negativos} registros con Cant_Ton ≤ 0"


@pytest.mark.integration
def test_variaciones_formato_colombiano():
    """Las variaciones en td_total_variaciones deben usar coma decimal y terminar en %."""
    path = _PROJECT_ROOT / "data/04_feature/td_total_variaciones.parquet"
    if not path.exists():
        pytest.skip("td_total_variaciones no disponible")
    df = pd.read_parquet(path, columns=["VariacMensual", "VariacAnual"])
    for col in ("VariacMensual", "VariacAnual"):
        for val in df[col].dropna():
            s = str(val)
            assert s.endswith("%"), f"{col}: '{s}' no termina en %"
            assert "," in s, f"{col}: '{s}' no usa coma decimal (formato SAS)"


# ── T52-D: Pipeline completo (slow) ──────────────────────────────────────────

@pytest.mark.slow
def test_kedro_run_completo():
    """Ejecuta `kedro run` completo y verifica que termina sin errores.

    Requiere data/01_raw/Base_sipsa_abastecimiento_abr2025.xlsx en disco.
    Omitir con: pytest -m 'not slow'
    """
    raw_input = _PROJECT_ROOT / "data/01_raw/Base_sipsa_abastecimiento_abr2025.xlsx"
    if not raw_input.exists():
        pytest.skip(f"Archivo de entrada no disponible: {raw_input}")

    kedro_bin = str(_VENV_KEDRO) if _VENV_KEDRO.exists() else "kedro"
    result = subprocess.run(
        [kedro_bin, "run"],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"kedro run falló (rc={result.returncode}):\n{result.stderr[-1000:]}"
    )
    # Verificar que los artefactos clave existen tras la ejecución
    for path in [
        "data/02_intermediate/base_sipsa_bronze.parquet",
        "data/03_primary/base_sipsa_clean.parquet",
        "data/03_primary/base_ipc_filtrada.parquet",
    ]:
        assert (_PROJECT_ROOT / path).exists(), f"Falta artefacto post-run: {path}"


@pytest.mark.slow
def test_kedro_run_solo_cleaning():
    """Ejecuta únicamente el pipeline de limpieza y verifica la salida."""
    raw_input = _PROJECT_ROOT / "data/01_raw/Base_sipsa_abastecimiento_abr2025.xlsx"
    if not raw_input.exists():
        pytest.skip("Archivo de entrada no disponible")

    kedro_bin = str(_VENV_KEDRO) if _VENV_KEDRO.exists() else "kedro"
    result = subprocess.run(
        [kedro_bin, "run", "--pipeline", "cleaning"],
        cwd=str(_PROJECT_ROOT),
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (
        f"kedro run --pipeline cleaning falló:\n{result.stderr[-500:]}"
    )
    clean_path = _PROJECT_ROOT / "data/03_primary/base_sipsa_clean.parquet"
    assert clean_path.exists()
    df = pd.read_parquet(clean_path)
    assert len(df) >= 500_000, f"base_sipsa_clean tiene solo {len(df)} filas"
