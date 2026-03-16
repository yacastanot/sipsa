"""Registro de pipelines del proyecto SIPSA."""
from kedro.pipeline import Pipeline

from sipsa.pipelines.ingestion.pipeline import create_pipeline as ingestion
from sipsa.pipelines.transformation.pipeline import create_pipeline as transformation
from sipsa.pipelines.aggregation.pipeline import create_pipeline as aggregation
from sipsa.pipelines.reporting.pipeline import create_pipeline as reporting


def register_pipelines() -> dict[str, Pipeline]:
    """Registra todos los pipelines del proyecto.

    Returns:
        Un diccionario con los pipelines disponibles.
        El pipeline "__default__" ejecuta el flujo completo.
    """
    ingestion_pipeline = ingestion()
    transformation_pipeline = transformation()
    aggregation_pipeline = aggregation()
    reporting_pipeline = reporting()

    return {
        "ingestion": ingestion_pipeline,
        "transformation": transformation_pipeline,
        "aggregation": aggregation_pipeline,
        "reporting": reporting_pipeline,
        "__default__": (
            ingestion_pipeline
            + transformation_pipeline
            + aggregation_pipeline
            + reporting_pipeline
        ),
    }
