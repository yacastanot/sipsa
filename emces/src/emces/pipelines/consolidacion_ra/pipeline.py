"""Pipeline de consolidación RA.

Consume:
    fletes_maestro   (producido por pipeline 'fletes')
    canc_maestro     (producido por pipeline 'cancilleria')

Produce:
    base_ra          (ParquetDataset — entrada del pipeline de encuesta)
    ra_resumen       (MemoryDataset  — metadata de auditoría)

Ejecución directa:
    kedro run --pipeline consolidacion_ra

Ejecución como parte del flujo RA completo (recomendado):
    kedro run --pipeline ra
    (= fletes + cancilleria + consolidacion_ra, definido en pipeline_registry.py)
"""
from kedro.pipeline import Pipeline, node, pipeline

from emces.pipelines.consolidacion_ra.nodes import consolidar_ra, generar_resumen_ra


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline(
        [
            node(
                func=consolidar_ra,
                inputs=["fletes_maestro", "canc_maestro"],
                outputs="base_ra",
                name="ra_consolidar",
            ),
            node(
                func=generar_resumen_ra,
                inputs="base_ra",
                outputs="ra_resumen",
                name="ra_generar_resumen",
            ),
        ]
    )
