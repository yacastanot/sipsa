"""Registro de pipelines del proyecto SIPSA IPC."""
from kedro.pipeline import Pipeline

from sipsa_ipc.pipelines.cleaning.pipeline import create_pipeline as cleaning_pipeline
from sipsa_ipc.pipelines.ingestion.pipeline import create_pipeline as ingestion_pipeline


def register_pipelines() -> dict[str, Pipeline]:
    ingestion = ingestion_pipeline()
    cleaning = cleaning_pipeline()

    return {
        "__default__": ingestion + cleaning,
        "ingestion": ingestion,
        "cleaning": cleaning,
        "silver": ingestion + cleaning,
    }
