"""Carga y caché de los parquets generados por el pipeline Kedro.

Todos los DataFrames se leen una vez al arrancar la app (lifespan) y se
guardan en el singleton ``store``.  Los routers los consultan mediante los
métodos de esta clase; nunca leen parquets directamente.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# Raíz del proyecto sipsa-ipc (cuatro niveles arriba de este archivo:
#   src/sipsa_ipc/api/data_store.py → src/sipsa_ipc/api/ → src/sipsa_ipc/ → src/ → sipsa-ipc/)
_PROJECT_ROOT = Path(__file__).parents[3]

_PATHS = {
    "td_total_variaciones": _PROJECT_ROOT / "data/04_feature/td_total_variaciones.parquet",
    "td_abast_fmt":         _PROJECT_ROOT / "data/04_feature/td_abast_fmt.parquet",
    "td_destino_fmt":       _PROJECT_ROOT / "data/04_feature/td_destino_fmt.parquet",
    "td_abast_otros_fmt":   _PROJECT_ROOT / "data/04_feature/td_abast_otros_fmt.parquet",
    "historico":            _PROJECT_ROOT / "data/07_model_output/historico_td_total.parquet",
}

MESES_ES = {
    "enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,
    "julio":7,"agosto":8,"septiembre":9,"octubre":10,"noviembre":11,"diciembre":12,
}


def parse_periodo(periodo: str) -> tuple[str, int]:
    """'Abril2025' → ('Abril', 2025).  Lanza ValueError si el formato es incorrecto."""
    periodo = periodo.strip()
    if len(periodo) < 5:
        raise ValueError(f"Período inválido: '{periodo}'")
    anio_str = periodo[-4:]
    mes_str = periodo[:-4]
    if not anio_str.isdigit():
        raise ValueError(f"Período inválido: '{periodo}'")
    mes_norm = mes_str.strip().capitalize()
    if mes_norm.casefold() not in MESES_ES:
        raise ValueError(f"Mes desconocido: '{mes_str}'")
    return mes_norm, int(anio_str)


class DataStore:
    """Singleton con los DataFrames cargados en memoria."""

    def __init__(self) -> None:
        self._td_total: pd.DataFrame = pd.DataFrame()
        self._td_abast: pd.DataFrame = pd.DataFrame()
        self._td_destino: pd.DataFrame = pd.DataFrame()
        self._td_abast_otros: pd.DataFrame = pd.DataFrame()
        self._historico: pd.DataFrame = pd.DataFrame()
        self.loaded = False

    def load(self) -> None:
        """Carga los parquets desde disco.  Llamar una sola vez al arrancar."""
        missing = [k for k, p in _PATHS.items() if not p.exists()]
        if missing:
            log.warning("Parquets no encontrados (ejecuta kedro run primero): %s", missing)

        def _read(key: str) -> pd.DataFrame:
            p = _PATHS[key]
            if p.exists():
                return pd.read_parquet(p)
            return pd.DataFrame()

        self._td_total = _read("td_total_variaciones")
        self._td_abast = _read("td_abast_fmt")
        self._td_destino = _read("td_destino_fmt")
        self._td_abast_otros = _read("td_abast_otros_fmt")
        self._historico = _read("historico")
        self.loaded = True
        log.info(
            "DataStore cargado | td_total=%d | td_abast=%d | td_destino=%d | "
            "td_abast_otros=%d | historico=%d",
            len(self._td_total), len(self._td_abast),
            len(self._td_destino), len(self._td_abast_otros), len(self._historico),
        )

    # ── /meses ────────────────────────────────────────────────────────────────

    def periodos_disponibles(self) -> list[dict]:
        if self._historico.empty:
            return []
        return (
            self._historico[["mes", "anio"]]
            .drop_duplicates()
            .sort_values(["anio", "mes"])
            .assign(periodo=lambda d: d["mes"] + d["anio"].astype(str))
            .to_dict(orient="records")
        )

    # ── /abastecimiento ───────────────────────────────────────────────────────

    def abastecimiento_por_articulo(self, codigo: int) -> pd.DataFrame:
        if self._td_abast.empty:
            return pd.DataFrame()
        return self._td_abast[self._td_abast["RArtículo_IPC"].eq(codigo)].copy()

    # ── /estadisticas ─────────────────────────────────────────────────────────

    def estadisticas_articulo(self, codigo: int) -> pd.Series | None:
        if self._td_total.empty:
            return None
        mask = self._td_total["RArtículo_IPC"].eq(codigo)
        if not mask.any():
            return None
        return self._td_total.loc[mask].iloc[0]

    def destinos_articulo(self, codigo: int) -> pd.DataFrame:
        if self._td_destino.empty:
            return pd.DataFrame()
        return self._td_destino[self._td_destino["RArtículo_IPC"].eq(codigo)].copy()

    def importaciones_articulo(self, codigo: int) -> pd.DataFrame:
        if self._td_abast_otros.empty:
            return pd.DataFrame()
        return self._td_abast_otros[self._td_abast_otros["RArtículo_IPC"].eq(codigo)].copy()

    # ── /comparacion ──────────────────────────────────────────────────────────

    def historico_periodo(self, mes: str, anio: int) -> pd.DataFrame:
        if self._historico.empty:
            return pd.DataFrame()
        mask = (
            self._historico["mes"].str.casefold().eq(mes.casefold())
            & self._historico["anio"].eq(anio)
        )
        return self._historico.loc[mask].copy()

    # ── helpers ───────────────────────────────────────────────────────────────

    def articulo_nombre(self, codigo: int) -> str | None:
        for df in (self._td_total, self._td_abast, self._td_destino):
            if df.empty:
                continue
            mask = df["RArtículo_IPC"].eq(codigo)
            if mask.any():
                return str(df.loc[mask, "Artículo_IPC"].iloc[0])
        return None

    def todos_los_codigos(self) -> list[int]:
        if self._td_total.empty:
            return []
        return sorted(self._td_total["RArtículo_IPC"].dropna().astype(int).unique().tolist())


store = DataStore()
