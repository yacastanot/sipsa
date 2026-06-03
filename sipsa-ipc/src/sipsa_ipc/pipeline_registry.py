"""Registro de pipelines del proyecto SIPSA IPC."""
from kedro.pipeline import Pipeline

from sipsa_ipc.pipelines.aggregation.pipeline import create_pipeline as aggregation_pipeline
from sipsa_ipc.pipelines.cleaning.pipeline import create_pipeline as cleaning_pipeline
from sipsa_ipc.pipelines.comparison.pipeline import create_pipeline as comparison_pipeline
from sipsa_ipc.pipelines.ingestion.pipeline import create_pipeline as ingestion_pipeline
from sipsa_ipc.pipelines.validation.pipeline import create_pipeline as validation_pipeline


def register_pipelines() -> dict[str, Pipeline]:
    ingestion = ingestion_pipeline()
    cleaning = cleaning_pipeline()
    validation = validation_pipeline()
    aggregation = aggregation_pipeline()
    comparison = comparison_pipeline()

    return {
        "__default__": ingestion + cleaning + validation + aggregation + comparison,
        "ingestion": ingestion,
        "cleaning": cleaning,
        "validation": validation,
        "aggregation": aggregation,
        "comparison": comparison,
        "silver": ingestion + cleaning,
        "f1": ingestion,
        "f2": cleaning,
        "f3": validation,
        "f4": aggregation,
        "f5": comparison,
    }
