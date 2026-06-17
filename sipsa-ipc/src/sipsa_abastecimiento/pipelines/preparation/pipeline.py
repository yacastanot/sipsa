"""Pipeline de preparación mensual — FASE 0."""
from kedro.pipeline import Pipeline, node, pipeline

from sipsa_abastecimiento.pipelines.preparation.nodes import preparar_articulos_ipc


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=preparar_articulos_ipc,
                inputs=[
                    "params:archivo_entrada",
                    "params:mes_actual_nombre",
                    "params:mes_anterior_nombre",
                    "params:anio_actual",
                    "params:anio_anterior",
                    "params:articulos_ipc",
                ],
                outputs="articulos_ipc_actualizado",
                name="preparar_articulos_ipc",
                tags=["preparation", "f0"],
            ),
        ]
    )
