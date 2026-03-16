"""Pipeline de agregación."""
from kedro.pipeline import Pipeline, node, pipeline

from .nodes import armar_cuadros


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=armar_cuadros,
                inputs=[
                    "precios_transformados",
                    "mapping_productos",
                    "mapping_cuadros",
                ],
                outputs="boletin_filas",
                name="armar_cuadros_node",
                tags=["aggregation"],
            ),
        ]
    )
