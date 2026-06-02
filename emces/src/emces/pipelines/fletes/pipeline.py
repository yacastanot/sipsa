from kedro.pipeline import Pipeline, node, pipeline

from emces.pipelines.fletes.nodes import (
    construir_registro_maestro,
    enriquecer_con_referencias,
    exportar_excel,
    leer_fletes,
    leer_m49,
    leer_pais,
    leer_trm,
    preparar_m49,
    unir_fletes_m49,
)


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            # ── Ingesta ───────────────────────────────────────────────────────
            node(
                func=leer_pais,
                inputs=["params:ruta_entrada", "params:archivo_parametricas"],
                outputs="raw_pais",
                name="leer_pais",
            ),
            node(
                func=leer_trm,
                inputs=["params:ruta_entrada", "params:archivo_parametricas"],
                outputs="raw_trm",
                name="leer_trm",
            ),
            node(
                func=leer_fletes,
                inputs=[
                    "params:ruta_entrada",
                    "params:archivo_fletes",
                    "params:ano",
                    "params:mes_numero",
                ],
                outputs="raw_fletes",
                name="leer_fletes",
            ),
            node(
                func=leer_m49,
                inputs=["params:ruta_entrada", "params:archivo_parametricas"],
                outputs="raw_m49",
                name="leer_m49",
            ),
            # ── Transformación ────────────────────────────────────────────────
            node(
                func=preparar_m49,
                inputs="raw_m49",
                outputs="m49_limpio",
                name="preparar_m49",
            ),
            node(
                func=unir_fletes_m49,
                inputs=["raw_fletes", "m49_limpio", "band_excluir", "params:ano"],
                outputs="fletes_filtrados",
                name="unir_fletes_m49",
            ),
            # ── Construcción ──────────────────────────────────────────────────
            node(
                func=enriquecer_con_referencias,
                inputs=[
                    "fletes_filtrados",
                    "raw_pais",
                    "raw_trm",
                    "params:ano",
                    "params:mes_numero",
                ],
                outputs="fletes_enriquecidos",
                name="enriquecer_con_referencias",
            ),
            node(
                func=construir_registro_maestro,
                inputs="fletes_enriquecidos",
                outputs="fletes_maestro",
                name="construir_registro_maestro",
            ),
            # ── Reporting ─────────────────────────────────────────────────────
            node(
                func=exportar_excel,
                inputs=[
                    "fletes_maestro",
                    "params:ano",
                    "params:mes_numero",
                    "params:ruta_salida",
                ],
                outputs="reporte_metadata",
                name="exportar_excel",
            ),
        ]
    )
