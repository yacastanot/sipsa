"""Patrón Strategy para la clasificación de modos de transporte (via).

El campo `via` del archivo de fletes determina cuatro campos de clasificación:
  - codigo        : código numérico del servicio
  - descripcion_cabps : descripción de la clasificación CABPS
  - cpc           : código CPC del servicio
  - descripcion_cpc   : descripción CPC

Cada modo de transporte (marítimo, carretera, aéreo) es una estrategia concreta
que implementa la interfaz abstracta ViaStrategy.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import pandas as pd

logger = logging.getLogger(__name__)


class ViaStrategy(ABC):
    """Interfaz abstracta: clasifica un modo de transporte en sus cuatro campos."""

    @property
    @abstractmethod
    def codigo(self) -> int: ...

    @property
    @abstractmethod
    def descripcion_cabps(self) -> str: ...

    @property
    @abstractmethod
    def cpc(self) -> str: ...

    @property
    @abstractmethod
    def descripcion_cpc(self) -> str: ...

    def as_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "descripcion_cabps": self.descripcion_cabps,
            "cpc": self.cpc,
            "descripcion_cpc": self.descripcion_cpc,
        }


class ViaMaritimaStrategy(ViaStrategy):
    """via = 1: Transporte marítimo de carga."""

    codigo = 208
    descripcion_cabps = "Transporte marítimo de carga"
    cpc = "65210"
    descripcion_cpc = "Servicios de transporte marítimo de carga"


class ViaCarreteraStrategy(ViaStrategy):
    """via = 3: Transporte de carga por carretera."""

    codigo = 225
    descripcion_cabps = "Transporte de carga por carretera"
    cpc = "65113"
    descripcion_cpc = "Servicios de transporte de carga por carretera en contenedores"


class ViaAereaStrategy(ViaStrategy):
    """via = 4: Transporte aéreo de carga."""

    codigo = 212
    descripcion_cabps = "Transporte aéreo de carga"
    cpc = "65310"
    descripcion_cpc = "Servicios de transporte de carga por vía aérea"


# Registro: valor entero de `via` → instancia singleton de su estrategia
VIA_STRATEGIES: dict[int, ViaStrategy] = {
    1: ViaMaritimaStrategy(),
    3: ViaCarreteraStrategy(),
    4: ViaAereaStrategy(),
}


def apply_via_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica la estrategia correspondiente a cada fila según el valor de `via`.

    Agrega las columnas: codigo, descripcion_cabps, cpc, descripcion_cpc.
    Las filas con valores de `via` desconocidos quedan con NaN en esas columnas
    y se registra una advertencia.
    """
    df = df.copy()
    for col in ("codigo", "descripcion_cabps", "cpc", "descripcion_cpc"):
        df[col] = None

    for via_val, strategy in VIA_STRATEGIES.items():
        mask = df["via"] == via_val
        for col, val in strategy.as_dict().items():
            df.loc[mask, col] = val

    unknown_mask = ~df["via"].isin(VIA_STRATEGIES)
    if unknown_mask.any():
        unknown_vals = sorted(df.loc[unknown_mask, "via"].dropna().unique().tolist())
        logger.warning(
            "%d filas tienen valores de 'via' no reconocidos: %s",
            unknown_mask.sum(),
            unknown_vals,
        )

    return df
