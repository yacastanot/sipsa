"""Pipeline de ingesta."""
from kedro.pipeline import Pipeline, node, pipeline

from .nodes import leer_entrada


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=leer_entrada,
                inputs=["params:ruta_entrada", "params:archivo_entrada"],
                outputs="precios_entrada",
                name="leer_entrada_node",
                tags=["ingestion"],
            ),
        ]
    )
