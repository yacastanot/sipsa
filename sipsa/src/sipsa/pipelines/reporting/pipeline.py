"""Pipeline de reporte."""
from kedro.pipeline import Pipeline, node, pipeline

from .nodes import generar_excel


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=generar_excel,
                inputs=[
                    "boletin_filas",
                    "params:fecha",
                    "params:ruta_salida",
                ],
                outputs="reporte_metadata",
                name="generar_excel_node",
                tags=["reporting"],
            ),
        ]
    )
