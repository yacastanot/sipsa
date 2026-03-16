"""Nodos de agregación: construye las filas del boletín agrupadas por cuadro.

Equivalente a los bloques %Prod, los DATA Cuadro1-8 y el DATA salida.Boletin del SAS.

Patrón Strategy: OrdenMercadosStrategy desacopla el criterio de ordenamiento
de mercados dentro de cada producto. Para cambiar el orden (p. ej. por precio)
basta con implementar una nueva subclase y pasarla a armar_cuadros.

Estructura de filas producida (columna _tipo):
  - 'cuadro'    : título del cuadro (ej. "Cuadro 1. ...")  → texto en negrita, sin precios
  - 'columnas'  : cabecera de columnas ("Productos y mercados", "Precio mínimo", ...) → negrita
  - 'producto'  : nombre del producto (ej. "Acelga") → negrita, sin precios
  - 'dato'      : fila de mercado con precios → texto normal
  - 'separador' : fila vacía entre productos
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)

COL_PM   = "Productos y mercados"
COL_MIN  = "Precio mínimo"
COL_MAX  = "Precio máximo"
COL_MED  = "Precio medio"
COL_TEND = "Tendencia"


# ─── Patrón Strategy: ordenamiento de mercados ───────────────────────────────

class OrdenMercadosStrategy(ABC):
    """Contrato para ordenar las filas de mercado dentro de un producto."""

    @abstractmethod
    def ordenar(self, datos_producto: pd.DataFrame) -> pd.DataFrame:
        """Devuelve `datos_producto` reordenado según el criterio de la estrategia."""


class OrdenPorCodigoLuegoAlfabetico(OrdenMercadosStrategy):
    """Mercados con código: orden ascendente por RFuente.
    Mercados sin código: orden alfabético por nombre de fuente, al final.

    Equivalente al comportamiento actual (más legible que el SAS, donde los
    valores nulos de RFuente ordenaban antes del encabezado del producto).
    """

    def ordenar(self, datos_producto: pd.DataFrame) -> pd.DataFrame:
        con_codigo = datos_producto[datos_producto["RFuente"].notna()].sort_values("RFuente")
        sin_codigo = datos_producto[datos_producto["RFuente"].isna()].sort_values("Fuente")
        return pd.concat([con_codigo, sin_codigo], ignore_index=True)


# Estrategia por defecto
_ORDEN_DEFAULT = OrdenPorCodigoLuegoAlfabetico()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _construir_mapa_inverso(mapping_productos: Dict[str, int]) -> Dict[int, str]:
    return {v: k for k, v in mapping_productos.items()}


def _fila(tipo: str, texto: str = "", min_=None, max_=None, med=None, tend: str = "") -> dict:
    return {
        COL_PM:   texto,
        COL_MIN:  min_,
        COL_MAX:  max_,
        COL_MED:  med,
        COL_TEND: tend,
        "_tipo":  tipo,
    }


# ─── Nodo Kedro ───────────────────────────────────────────────────────────────

def armar_cuadros(
    df: pd.DataFrame,
    mapping_productos: Dict[str, int],
    config_cuadros: Dict[str, Any],
    orden_mercados: OrdenMercadosStrategy = _ORDEN_DEFAULT,
) -> pd.DataFrame:
    """Construye el DataFrame completo de filas del boletín en el orden del SAS.

    Para cada cuadro (1-8):
      1. Añade la fila de título del cuadro.
      2. Añade la fila de cabecera de columnas (excepto en el Cuadro 1, donde se
         incluye al inicio del archivo).
      3. Para cada producto en el orden definido:
         a. Si no tiene datos en esta semana → se omite (equivale a suma_first=2 en SAS).
         b. Si tiene datos: fila de nombre del producto + filas de mercado + separador.

    El orden de las filas de mercado dentro de cada producto queda delegado a
    `orden_mercados` (Strategy). Por defecto: mapeados por código, sin mapear al final.

    Args:
        df: DataFrame transformado con columnas Rproducto, RFuente, Fuente, etc.
        mapping_productos: Dict {nombre_producto: código}.
        config_cuadros: Contenido de cuadros.yml → dict con clave 'cuadros'.
        orden_mercados: Estrategia de ordenamiento de mercados dentro de cada producto.

    Returns:
        DataFrame con todas las filas del boletín y columna _tipo.
    """
    mapa_inverso = _construir_mapa_inverso(mapping_productos)
    cuadros_cfg  = config_cuadros["cuadros"]

    filas: List[dict] = []
    fila_col = _fila("columnas", texto="Productos y mercados")

    # Cabecera inicial (antes del Cuadro 1)
    filas.append(fila_col)

    for num_cuadro in sorted(cuadros_cfg.keys()):
        cfg             = cuadros_cfg[num_cuadro]
        titulo          = cfg["titulo"]
        orden_productos = cfg["productos"]

        filas.append(_fila("cuadro", texto=titulo))

        if num_cuadro != min(cuadros_cfg.keys()):
            filas.append(fila_col)

        productos_con_datos = 0

        for codigo in orden_productos:
            datos_producto = df[df["Rproducto"] == codigo]
            if datos_producto.empty:
                continue

            nombre = mapa_inverso.get(codigo, f"[código {codigo}]")
            productos_con_datos += 1

            filas.append(_fila("producto", texto=nombre))

            for _, row in orden_mercados.ordenar(datos_producto).iterrows():
                filas.append(
                    _fila(
                        "dato",
                        texto=row["Fuente"],
                        min_=row["Min(1)"],
                        max_=row["Max(1)"],
                        med=row["P(1)"],
                        tend=str(row["Tend"]),
                    )
                )

            filas.append(_fila("separador"))

        logger.info("Cuadro %d: %d productos con datos.", num_cuadro, productos_con_datos)

    resultado = pd.DataFrame(filas)

    resultado[COL_PM] = resultado[COL_PM].astype(str).where(resultado[COL_PM].notna(), None)
    for col_precio in [COL_MIN, COL_MAX, COL_MED]:
        resultado[col_precio] = pd.to_numeric(resultado[col_precio], errors="coerce")
    resultado[COL_TEND] = resultado[COL_TEND].astype(str)
    resultado["_tipo"]  = resultado["_tipo"].astype(str)

    logger.info("Boletín armado: %d filas totales.", len(resultado))
    return resultado
