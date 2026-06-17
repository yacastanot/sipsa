"""Pipeline de validación — FASE 3."""
from kedro.pipeline import Pipeline, node, pipeline

from sipsa_abastecimiento.pipelines.validation.nodes import (
    calcular_cobertura,
    filtrar_articulos_canasta,
    generar_no_mapeados,
)


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=filtrar_articulos_canasta,
                inputs="base_sipsa_clean",
                outputs="base_ipc_filtrada",
                name="filtrar_articulos_canasta",
                tags=["validation", "f3"],
            ),
            node(
                func=generar_no_mapeados,
                inputs="base_sipsa_clean",
                outputs="no_mapeados_ipc",
                name="generar_no_mapeados",
                tags=["validation", "f3"],
            ),
            node(
                func=calcular_cobertura,
                inputs=[
                    "base_ipc_filtrada",
                    "articulos_ipc_actualizado",
                    "params:mes_actual_nombre",
                    "params:anio_actual",
                ],
                outputs="cobertura_ipc",
                name="calcular_cobertura",
                tags=["validation", "f3"],
            ),
        ]
    )
