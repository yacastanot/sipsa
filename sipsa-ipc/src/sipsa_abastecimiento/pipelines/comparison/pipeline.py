"""Pipeline de análisis comparativo interperiódico — FASE 5."""
from kedro.pipeline import Pipeline, node, pipeline

from sipsa_abastecimiento.pipelines.comparison.nodes import calcular_variaciones


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=calcular_variaciones,
                inputs="td_total",
                outputs="td_total_variaciones",
                name="calcular_variaciones",
                tags=["comparison", "f5"],
            ),
        ]
    )
