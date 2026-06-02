"""Pipeline de Unión de Base RA — acumulación histórica mensual.

Propósito
─────────────────────────────────────────────────────────────────────────────
Implementa el script SAS 'UnirBase F2026_01C2026_01.sas'.
Cada mes se ejecuta DESPUÉS de correr los pipelines de fuentes (fletes,
cancillería) para:
  1. Cargar la base RA acumulada del mes anterior (Excel histórico).
  2. Agregar el mes corriente según fuentes_activas en parameters.yml.
  3. Ordenar por PERIODO_MES.
  4. Exportar el nuevo Excel histórico con nombre dinámico.

Flujo de datasets
─────────────────────────────────────────────────────────────────────────────
  [Excel histórico]     → leer_base_historica → ra_historico ──┐
  fletes_maestro ────────────────────────────────────────────────┤
  canc_maestro ──────────────────────────────────────────────────┤→ acumular_fuentes
  params fuentes_activas ────────────────────────────────────────┘
                                  ↓
                         base_ra_acumulada (Parquet)
                                  ↓
                         exportar_base_acumulada → union_ra_metadata

Ejecución mensual
─────────────────────────────────────────────────────────────────────────────
  1. Correr fletes:      kedro run --pipeline fletes
  2. Correr cancillería: kedro run --pipeline cancilleria  (si activa)
  3. Correr unión:       kedro run --pipeline union_ra

  O en una sola ejecución (flujo RA completo):
                         kedro run --pipeline ra_completo
  (definido en pipeline_registry.py)

Activar Cancillería
─────────────────────────────────────────────────────────────────────────────
  En conf/base/parameters.yml:
    union_ra:
      fuentes_activas:
        fletes: true
        cancilleria: true   ← cambiar de false a true
      anoc: "26"
      mesc: "01"
"""
from kedro.pipeline import Pipeline, node, pipeline

from emces.pipelines.union_ra.nodes import (
    acumular_fuentes,
    exportar_base_acumulada,
    leer_base_historica,
)


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            # ── 1. Leer histórico ─────────────────────────────────────────────
            # Equivale a: PROC IMPORT OUT=RA_0 DATAFILE="...BaseEMCES-RA_...xlsx"
            node(
                func=leer_base_historica,
                inputs=[
                    "params:ruta_primary",
                    "params:union_ra.archivo_historico",
                    "params:union_ra.hoja_historico",
                ],
                outputs="ra_historico",
                name="union_ra_leer_historico",
            ),
            # ── 2. Acumular fuentes + ordenar ────────────────────────────────
            # Equivale a: DATA RA_1; SET RA_0 FLETES_1 [CANCILLERIA_1];
            #             PROC SORT DATA=RA_1; BY PERIODO_MES;
            node(
                func=acumular_fuentes,
                inputs=[
                    "ra_historico",
                    "fletes_maestro",
                    "canc_maestro",
                    "params:union_ra.fuentes_activas",
                ],
                outputs="base_ra_acumulada",
                name="union_ra_acumular",
            ),
            # ── 3. Exportar Excel con nombre dinámico ─────────────────────────
            # Equivale a: PROC EXPORT OUTFILE="...F&ANOF.&MESF.C&ANOC.&MESC..xlsx"
            node(
                func=exportar_base_acumulada,
                inputs=[
                    "base_ra_acumulada",
                    "params:ruta_primary",
                    "params:union_ra.prefijo_salida",
                    "params:union_ra.anof",
                    "params:union_ra.mesf",
                    "params:union_ra.anoc",
                    "params:union_ra.mesc",
                    "params:union_ra.hoja_salida",
                ],
                outputs="union_ra_metadata",
                name="union_ra_exportar",
            ),
        ]
    )
