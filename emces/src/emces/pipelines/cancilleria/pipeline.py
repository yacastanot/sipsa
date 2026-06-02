"""Pipeline de Cancillería EMCES.

Flujo completo de 14 nodos en 4 etapas:
    ingesta       → 5 nodos (lectura de Excel)
    transformación → 5 nodos (BASE1 → BASE4)
    agregación    → 1 nodo  (BASE5 GROUP BY)
    enriquecimiento→ 1 nodo  (BASE6 + PAISES1)
    reporting     → 2 nodos (layout EMCES + exportación)

Ejecución mensual:
    1. Copiar archivo base a data/01_raw/
    2. Actualizar conf/base/parameters.yml: cancilleria.periodo, .mes, .mes_nombre, .archivo_base
    3. kedro run --pipeline cancilleria
"""
from kedro.pipeline import Pipeline, node, pipeline

from emces.pipelines.cancilleria.nodes import (
    agregar_por_pais,
    calcular_campos_monetarios,
    construir_base1,
    construir_layout_emces,
    enriquecer_con_acuerdos,
    enriquecer_con_paises,
    enriquecer_con_trm,
    exportar_excel,
    filtrar_y_transformar_trm,
    leer_devengados,
    leer_gastos,
    leer_paises_acuerdos_cancilleria,
    leer_paises_cancilleria,
    leer_trm_cancilleria,
)


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            # ── Ingesta ───────────────────────────────────────────────────────
            node(
                func=leer_devengados,
                inputs=[
                    "params:ruta_entrada",
                    "params:cancilleria.archivo_base",
                    "params:cancilleria.hojas.devengados",
                ],
                outputs="canc_raw_devengados",
                name="canc_leer_devengados",
            ),
            node(
                func=leer_gastos,
                inputs=[
                    "params:ruta_entrada",
                    "params:cancilleria.archivo_base",
                    "params:cancilleria.hojas.gastos",
                ],
                outputs="canc_raw_gastos",
                name="canc_leer_gastos",
            ),
            node(
                func=leer_trm_cancilleria,
                inputs=[
                    "params:ruta_entrada",
                    "params:archivo_parametricas",
                    "params:cancilleria.hojas.trm",
                ],
                outputs="canc_raw_trm",
                name="canc_leer_trm",
            ),
            node(
                func=leer_paises_cancilleria,
                inputs=[
                    "params:ruta_entrada",
                    "params:archivo_parametricas",
                    "params:cancilleria.hojas.paises",
                ],
                outputs="canc_raw_paises",
                name="canc_leer_paises",
            ),
            node(
                func=leer_paises_acuerdos_cancilleria,
                inputs=[
                    "params:ruta_entrada",
                    "params:archivo_parametricas",
                    "params:cancilleria.hojas.paises1",
                ],
                outputs="canc_raw_paises1",
                name="canc_leer_paises_acuerdos",
            ),
            # ── Transformación ────────────────────────────────────────────────
            node(
                func=construir_base1,
                inputs=[
                    "canc_raw_devengados",
                    "canc_raw_gastos",
                    "params:cancilleria.periodo",
                    "params:cancilleria.mes",
                ],
                outputs="canc_base1",
                name="canc_construir_base1",
            ),
            node(
                func=filtrar_y_transformar_trm,
                inputs=[
                    "canc_raw_trm",
                    "params:cancilleria.periodo",
                    "params:cancilleria.mes",
                ],
                outputs="canc_trm_largo",
                name="canc_filtrar_trm",
            ),
            node(
                func=enriquecer_con_paises,
                inputs=["canc_base1", "canc_raw_paises"],
                outputs="canc_base2",
                name="canc_enriquecer_paises",
            ),
            node(
                func=enriquecer_con_trm,
                inputs=["canc_base2", "canc_trm_largo"],
                outputs="canc_base3",
                name="canc_enriquecer_trm",
            ),
            node(
                func=calcular_campos_monetarios,
                inputs="canc_base3",
                outputs="canc_base4",
                name="canc_calcular_monetarios",
            ),
            # ── Agregación ────────────────────────────────────────────────────
            node(
                func=agregar_por_pais,
                inputs="canc_base4",
                outputs="canc_base5",
                name="canc_agregar_por_pais",
            ),
            # ── Enriquecimiento final ─────────────────────────────────────────
            node(
                func=enriquecer_con_acuerdos,
                inputs=["canc_base5", "canc_raw_paises1"],
                outputs="canc_base6",
                name="canc_enriquecer_acuerdos",
            ),
            # ── Reporting ─────────────────────────────────────────────────────
            node(
                func=construir_layout_emces,
                inputs=[
                    "canc_base6",
                    "params:cancilleria.periodo",
                    "params:cancilleria.mes",
                    "params:cancilleria.mes_nombre",
                ],
                outputs="canc_maestro",
                name="canc_construir_layout",
            ),
            node(
                func=exportar_excel,
                inputs=[
                    "canc_maestro",
                    "params:ruta_salida",
                    "params:cancilleria.periodo",
                    "params:cancilleria.mes",
                ],
                outputs="canc_reporte_metadata",
                name="canc_exportar_excel",
            ),
        ]
    )
