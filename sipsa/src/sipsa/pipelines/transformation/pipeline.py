"""Pipeline de transformación."""
from kedro.pipeline import Pipeline, node, pipeline

from .nodes import aplicar_mappings


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=aplicar_mappings,
                inputs=[
                    "precios_entrada",
                    "mapping_productos",
                    "mapping_fuentes",
                    "mapping_grupos",
                ],
                outputs="precios_transformados",
                name="aplicar_mappings_node",
                tags=["transformation"],
            ),
        ]
    )
