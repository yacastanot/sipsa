"""Pipeline de generación de reportes — FASE 7."""
from kedro.pipeline import Pipeline, node, pipeline

from sipsa_ipc.pipelines.reporting.nodes import (
    exportar_alimentos_priorizados,
    exportar_sipsa_ipc,
    guardar_historico,
)


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=exportar_sipsa_ipc,
                inputs=[
                    "td_total_variaciones",
                    "td_abast_fmt",
                    "td_destino_fmt",
                    "td_abast_otros_fmt",
                    "articulos_ipc_actualizado",
                    "params:fecha_proceso",
                    "params:ruta_reporting",
                ],
                outputs="metadata_sipsa_ipc",
                name="exportar_sipsa_ipc",
                tags=["reporting", "f7"],
            ),
            node(
                func=exportar_alimentos_priorizados,
                inputs=[
                    "td_total_variaciones",
                    "td_abast_fmt",
                    "td_destino_fmt",
                    "td_abast_otros_fmt",
                    "params:mes_actual_nombre",
                    "params:anio_actual",
                    "params:fecha_proceso",
                    "params:ruta_reporting",
                    "params:archivo_entrada",
                ],
                outputs="metadata_alimentos_priorizados",
                name="exportar_alimentos_priorizados",
                tags=["reporting", "f7"],
            ),
            node(
                func=guardar_historico,
                inputs=[
                    "td_total_variaciones",
                    "params:mes_actual_nombre",
                    "params:anio_actual",
                ],
                outputs="historico_td_total",
                name="guardar_historico",
                tags=["reporting", "f7"],
            ),
        ]
    )
