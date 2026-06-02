"""
Pruebas de calidad: compara el archivo generado por el pipeline Python
contra el archivo de referencia generado por el script R original.

Cómo ejecutar:
    .venv/Scripts/python.exe -m pytest tests/test_calidad.py -v

Tolerancias numéricas:
    - Absoluta: 1e-6  (cubre errores de redondeo de punto flotante)
    - Relativa: 1e-9  (cubre diferencias de precisión en operaciones /)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ── Rutas ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parents[1]
REPORTING = ROOT / "data" / "08_reporting"

ARCHIVO_PYTHON = REPORTING / "Fletes_EMCES_2025_12_python.xlsx"
ARCHIVO_R      = REPORTING / "Fletes_EMCES_2025_12_salidaR.xlsx"

HOJA_ESPERADA  = "Fletes_EMCES_2025_12"

# Tolerancias para columnas numéricas monetarias
TOL_ABS = 1e-6
TOL_REL = 1e-9

# Columnas numéricas a comparar con tolerancia
COLS_NUMERICAS = ["TOTAL_EN_DOLARES", "TOTAL_EN_MILES_DE_PESOS", "TRM_BASE"]

# Columnas clave de negocio que no deben tener nulos
COLS_OBLIGATORIAS = [
    "FLUJO_COMERCIAL", "IDNOREMP", "PERIODO", "MES", "PAIS",
    "CODIGO", "CPC", "TOTAL_EN_DOLARES",
]

# Códigos de vía válidos (CODIGO en la salida)
CODIGOS_VIA_VALIDOS = {208, 212, 225}

# Distribución esperada de filas por modo (conteos verificados contra R)
DISTRIBUCION_ESPERADA = {208: 104, 212: 82, 225: 64}


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _cargar(path: Path) -> pd.DataFrame:
    """Carga el Excel completo como string y normaliza nombres de columna."""
    df = pd.read_excel(path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    return df


def _ordenar(df: pd.DataFrame) -> pd.DataFrame:
    """Ordena por (MES, PAIS, CODIGO) para comparación posicional."""
    return df.sort_values(["MES", "PAIS", "CODIGO"]).reset_index(drop=True)


@pytest.fixture(scope="module")
def df_python() -> pd.DataFrame:
    return _cargar(ARCHIVO_PYTHON)


@pytest.fixture(scope="module")
def df_r() -> pd.DataFrame:
    return _cargar(ARCHIVO_R)


@pytest.fixture(scope="module")
def df_python_ord(df_python) -> pd.DataFrame:
    return _ordenar(df_python)


@pytest.fixture(scope="module")
def df_r_ord(df_r) -> pd.DataFrame:
    return _ordenar(df_r)


# ── Pruebas de estructura ──────────────────────────────────────────────────────

class TestEstructura:
    def test_archivos_existen(self):
        assert ARCHIVO_PYTHON.exists(), f"No se encontró el archivo Python: {ARCHIVO_PYTHON}"
        assert ARCHIVO_R.exists(),      f"No se encontró el archivo R: {ARCHIVO_R}"

    def test_nombre_hoja_python(self):
        hojas = pd.ExcelFile(ARCHIVO_PYTHON).sheet_names
        assert HOJA_ESPERADA in hojas, (
            f"Hoja '{HOJA_ESPERADA}' no encontrada. Hojas disponibles: {hojas}"
        )

    def test_nombre_hoja_r(self):
        hojas = pd.ExcelFile(ARCHIVO_R).sheet_names
        assert HOJA_ESPERADA in hojas, (
            f"Hoja '{HOJA_ESPERADA}' no encontrada. Hojas disponibles: {hojas}"
        )

    def test_mismo_numero_de_filas(self, df_python, df_r):
        assert len(df_python) == len(df_r), (
            f"Filas Python={len(df_python)}, R={len(df_r)}"
        )

    def test_mismo_numero_de_columnas(self, df_python, df_r):
        assert len(df_python.columns) == len(df_r.columns), (
            f"Columnas Python={len(df_python.columns)}, R={len(df_r.columns)}"
        )

    def test_mismas_columnas(self, df_python, df_r):
        cols_py = set(df_python.columns)
        cols_r  = set(df_r.columns)
        solo_py = cols_py - cols_r
        solo_r  = cols_r  - cols_py
        assert not solo_py and not solo_r, (
            f"Solo en Python: {solo_py} | Solo en R: {solo_r}"
        )

    def test_orden_columnas_identico(self, df_python, df_r):
        assert list(df_python.columns) == list(df_r.columns), (
            "El orden de las columnas difiere entre Python y R."
        )


# ── Pruebas de contenido no numérico ──────────────────────────────────────────

class TestContenidoCategorico:
    def test_flujo_comercial(self, df_python):
        valores = df_python["FLUJO_COMERCIAL"].unique()
        assert list(valores) == ["IMPORTACIONES FLETES"], (
            f"FLUJO_COMERCIAL inesperado: {valores}"
        )

    def test_idnoremp(self, df_python):
        assert (df_python["IDNOREMP"] == "777-1").all(), \
            "IDNOREMP debe ser '777-1' en todas las filas."

    def test_periodo(self, df_python):
        assert (df_python["PERIODO"] == "2025").all(), \
            "PERIODO debe ser '2025' en todas las filas."

    def test_mes(self, df_python):
        assert (df_python["MES"] == "12").all(), \
            "MES debe ser '12' en todas las filas."

    def test_columnas_texto_identicas(self, df_python_ord, df_r_ord):
        """Compara todas las columnas no numéricas fila a fila."""
        cols_texto = [c for c in df_python_ord.columns if c not in COLS_NUMERICAS]
        for col in cols_texto:
            py_vals = df_python_ord[col].str.strip().fillna("")
            r_vals  = df_r_ord[col].str.strip().fillna("")
            mask = py_vals != r_vals
            assert not mask.any(), (
                f"Columna '{col}' difiere en {mask.sum()} filas.\n"
                f"  Python: {py_vals[mask].head(3).tolist()}\n"
                f"  R:      {r_vals[mask].head(3).tolist()}"
            )


# ── Pruebas numéricas con tolerancia ──────────────────────────────────────────

class TestContenidoNumerico:
    @pytest.mark.parametrize("col", COLS_NUMERICAS)
    def test_columna_numerica_dentro_tolerancia(self, df_python_ord, df_r_ord, col):
        py = pd.to_numeric(df_python_ord[col], errors="coerce")
        r  = pd.to_numeric(df_r_ord[col],      errors="coerce")
        diff_abs = (py - r).abs()
        diff_rel = diff_abs / r.abs().replace(0, np.nan)
        fuera = (diff_abs > TOL_ABS) & (diff_rel > TOL_REL)
        assert not fuera.any(), (
            f"Columna '{col}': {fuera.sum()} filas fuera de tolerancia "
            f"(abs={TOL_ABS}, rel={TOL_REL}).\n"
            f"  Max diff absoluta: {diff_abs.max():.2e}\n"
            f"  Max diff relativa: {diff_rel.max():.2e}"
        )

    def test_total_en_dolares_suma(self, df_python, df_r):
        suma_py = pd.to_numeric(df_python["TOTAL_EN_DOLARES"], errors="coerce").sum()
        suma_r  = pd.to_numeric(df_r["TOTAL_EN_DOLARES"],      errors="coerce").sum()
        assert abs(suma_py - suma_r) < TOL_ABS, (
            f"Suma TOTAL_EN_DOLARES: Python={suma_py:.6f}, R={suma_r:.6f}"
        )

    def test_total_en_miles_pesos_suma(self, df_python, df_r):
        suma_py = pd.to_numeric(df_python["TOTAL_EN_MILES_DE_PESOS"], errors="coerce").sum()
        suma_r  = pd.to_numeric(df_r["TOTAL_EN_MILES_DE_PESOS"],      errors="coerce").sum()
        rel = abs(suma_py - suma_r) / abs(suma_r)
        assert rel < TOL_REL * 1e4, (
            f"Suma TOTAL_EN_MILES_DE_PESOS: Python={suma_py:.2f}, R={suma_r:.2f} "
            f"(diff relativa={rel:.2e})"
        )

    def test_no_hay_negativos_en_total_dolares(self, df_python):
        vals = pd.to_numeric(df_python["TOTAL_EN_DOLARES"], errors="coerce")
        assert (vals >= 0).all(), \
            f"Hay {(vals < 0).sum()} filas con TOTAL_EN_DOLARES negativo."


# ── Pruebas de reglas de negocio ───────────────────────────────────────────────

class TestReglasDeNegocio:
    def test_codigos_via_validos(self, df_python):
        codigos = set(pd.to_numeric(df_python["CODIGO"], errors="coerce").dropna().astype(int))
        invalidos = codigos - CODIGOS_VIA_VALIDOS
        assert not invalidos, (
            f"Códigos de vía no reconocidos: {invalidos}. Válidos: {CODIGOS_VIA_VALIDOS}"
        )

    def test_distribucion_por_codigo(self, df_python):
        conteos = (
            pd.to_numeric(df_python["CODIGO"], errors="coerce")
            .astype("Int64")
            .value_counts()
            .to_dict()
        )
        for codigo, esperado in DISTRIBUCION_ESPERADA.items():
            real = conteos.get(codigo, 0)
            assert real == esperado, (
                f"CODIGO={codigo}: esperado {esperado} filas, encontrado {real}"
            )

    @pytest.mark.parametrize("col", COLS_OBLIGATORIAS)
    def test_sin_nulos_en_columnas_clave(self, df_python, col):
        nulos = df_python[col].isna() | (df_python[col].str.strip() == "")
        assert not nulos.any(), (
            f"Columna obligatoria '{col}' tiene {nulos.sum()} valores nulos/vacíos."
        )

    def test_combinacion_pais_mes_codigo_unica(self, df_python):
        dupes = df_python.duplicated(subset=["PAIS", "MES", "CODIGO"]).sum()
        assert dupes == 0, (
            f"Hay {dupes} combinaciones duplicadas de (PAIS, MES, CODIGO)."
        )

    def test_cpc_coherente_con_codigo(self, df_python):
        mapa_cpc = {
            "208": "65210",  # Marítimo
            "212": "65310",  # Aéreo
            "225": "65113",  # Carretera
        }
        for codigo, cpc_esperado in mapa_cpc.items():
            mask = df_python["CODIGO"] == codigo
            cpcs = df_python.loc[mask, "CPC"].unique()
            assert list(cpcs) == [cpc_esperado], (
                f"CODIGO={codigo} → CPC esperado '{cpc_esperado}', encontrado: {cpcs}"
            )

    def test_descripcion_modo_constante(self, df_python):
        desc_esperada = (
            "El proveedor y consumidor permanecen en sus respectivos territorios, "
            "solo se desplaza el servicio."
        )
        assert (df_python["DESCRIPCION_MODO"].str.strip() == desc_esperada).all(), \
            "DESCRIPCION_MODO no es constante en todas las filas."

    def test_agrupacion_constante(self, df_python):
        assert (pd.to_numeric(df_python["AGRUPACION"], errors="coerce") == 3).all(), \
            "AGRUPACION debe ser 3 en todas las filas."
