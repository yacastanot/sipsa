"""Pipeline de formato, normalización y ordenamiento — FASE 6."""
from kedro.pipeline import Pipeline, node, pipeline

from sipsa_abastecimiento.pipelines.formatting.nodes import (
    formatear_td_abast,
    formatear_td_abast_otros,
    formatear_td_destino,
)


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=formatear_td_abast,
                inputs="td_abast",
                outputs="td_abast_fmt",
                name="formatear_td_abast",
                tags=["formatting", "f6"],
            ),
            node(
                func=formatear_td_destino,
                inputs="td_destino",
                outputs="td_destino_fmt",
                name="formatear_td_destino",
                tags=["formatting", "f6"],
            ),
            node(
                func=formatear_td_abast_otros,
                inputs="td_abast_otros",
                outputs="td_abast_otros_fmt",
                name="formatear_td_abast_otros",
                tags=["formatting", "f6"],
            ),
        ]
    )
