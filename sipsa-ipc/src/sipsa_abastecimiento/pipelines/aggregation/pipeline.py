"""Pipeline de agregación — FASE 4."""
from kedro.pipeline import Pipeline, node, pipeline

from sipsa_abastecimiento.pipelines.aggregation.nodes import (
    calcular_td_abast,
    calcular_td_abast_otros,
    calcular_td_destino,
    calcular_td_total,
)


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=calcular_td_total,
                inputs="base_ipc_filtrada",
                outputs="td_total",
                name="calcular_td_total",
                tags=["aggregation", "f4"],
            ),
            node(
                func=calcular_td_abast,
                inputs="base_ipc_filtrada",
                outputs="td_abast",
                name="calcular_td_abast",
                tags=["aggregation", "f4"],
            ),
            node(
                func=calcular_td_destino,
                inputs="base_ipc_filtrada",
                outputs="td_destino",
                name="calcular_td_destino",
                tags=["aggregation", "f4"],
            ),
            node(
                func=calcular_td_abast_otros,
                inputs="base_ipc_filtrada",
                outputs="td_abast_otros",
                name="calcular_td_abast_otros",
                tags=["aggregation", "f4"],
            ),
        ]
    )
