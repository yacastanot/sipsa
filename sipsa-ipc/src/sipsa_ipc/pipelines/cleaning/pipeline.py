"""Pipeline de limpieza - FASE 2."""
from kedro.pipeline import Pipeline, node, pipeline

from sipsa_ipc.pipelines.cleaning.nodes import limpiar_base


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=limpiar_base,
                inputs=[
                    "base_sipsa_bronze",
                    "params:articulos_ipc",
                    "params:mes_actual_nombre",
                    "params:mes_anterior_nombre",
                    "params:anio_actual",
                    "params:anio_anterior",
                ],
                outputs="base_sipsa_clean",
                name="limpiar_base",
                tags=["cleaning", "f2"],
            ),
        ]
    )
