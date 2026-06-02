"""Pipeline de ingesta — FASE 1: Capa de Ingesta de Datos.

Grafo:
  params:archivo_entrada ──► [leer_base] ──► base_sipsa_bronze

El nodo recibe la ruta del Excel como parámetro y lo lee directamente.
La salida (bronze) se persiste en Parquet para F2 en adelante.
"""
from kedro.pipeline import Pipeline, node, pipeline

from sipsa_ipc.pipelines.ingestion.nodes import leer_base


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=leer_base,
                inputs="params:archivo_entrada",
                outputs="base_sipsa_bronze",
                name="leer_base",
                tags=["ingestion", "f1"],
            ),
        ]
    )
