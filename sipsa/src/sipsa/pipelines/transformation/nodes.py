"""Nodos de transformación: aplicación de mappings (producto → código, fuente → código, grupo → código)."""
import logging
from typing import Any, Dict

import pandas as pd

logger = logging.getLogger(__name__)


def aplicar_mappings(
    df: pd.DataFrame,
    mapping_productos: Dict[str, int],
    mapping_fuentes: Dict[str, int],
    mapping_grupos: Dict[str, int],
) -> pd.DataFrame:
    """Añade columnas con los códigos numéricos de producto, fuente y grupo.

    Equivalente al DATA Boletin1 del SAS: agrega Rproducto, RFuente y RGrupo.
    Los registros que no tengan un Rproducto conocido se descartan (no aparecen
    en ningún cuadro del boletín).

    Args:
        df: DataFrame validado de la etapa de ingesta.
        mapping_productos: Dict {nombre_producto: código}.
        mapping_fuentes: Dict {nombre_fuente: código}.
        mapping_grupos: Dict {nombre_grupo: código}.

    Returns:
        DataFrame enriquecido con columnas Rproducto, RFuente, RGrupo.
    """
    resultado = df.copy()

    resultado["Rproducto"] = resultado["Producto"].map(mapping_productos)
    resultado["RFuente"] = resultado["Fuente"].map(mapping_fuentes)
    resultado["RGrupo"] = resultado["Grupo"].map(mapping_grupos)

    # Productos sin mapping → no pertenecen al catálogo oficial, se excluyen
    sin_codigo = resultado["Rproducto"].isna()
    if sin_codigo.any():
        productos_desconocidos = sorted(resultado.loc[sin_codigo, "Producto"].unique())
        logger.warning(
            "%d filas excluidas por productos sin código en el catálogo: %s",
            sin_codigo.sum(),
            productos_desconocidos,
        )
    resultado = resultado[~sin_codigo].copy()
    resultado["Rproducto"] = resultado["Rproducto"].astype(int)

    # Fuentes sin mapping → se incluyen pero sin código (se ordenan al final de cada producto)
    sin_fuente = resultado["RFuente"].isna()
    if sin_fuente.any():
        fuentes_desconocidas = sorted(resultado.loc[sin_fuente, "Fuente"].unique())
        logger.warning(
            "%d filas con fuentes sin código (se incluirán sin orden específico): %s",
            sin_fuente.sum(),
            fuentes_desconocidas,
        )

    logger.info(
        "Transformación completada: %d filas, %d productos únicos mapeados.",
        len(resultado),
        resultado["Rproducto"].nunique(),
    )
    return resultado
