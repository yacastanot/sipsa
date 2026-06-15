"""Registro de pipelines del proyecto SIPSA IPC."""
from kedro.pipeline import Pipeline

from sipsa_ipc.pipelines.aggregation.pipeline import create_pipeline as aggregation_pipeline
from sipsa_ipc.pipelines.cleaning.pipeline import create_pipeline as cleaning_pipeline
from sipsa_ipc.pipelines.comparison.pipeline import create_pipeline as comparison_pipeline
from sipsa_ipc.pipelines.formatting.pipeline import create_pipeline as formatting_pipeline
from sipsa_ipc.pipelines.ingestion.pipeline import create_pipeline as ingestion_pipeline
from sipsa_ipc.pipelines.preparation.pipeline import create_pipeline as preparation_pipeline
from sipsa_ipc.pipelines.reporting.pipeline import create_pipeline as reporting_pipeline
from sipsa_ipc.pipelines.validation.pipeline import create_pipeline as validation_pipeline


def register_pipelines() -> dict[str, Pipeline]:
    preparation = preparation_pipeline()
    ingestion   = ingestion_pipeline()
    cleaning    = cleaning_pipeline()
    validation  = validation_pipeline()
    aggregation = aggregation_pipeline()
    formatting  = formatting_pipeline()
    comparison  = comparison_pipeline()
    reporting   = reporting_pipeline()

    return {
        "__default__": preparation + ingestion + cleaning + validation + aggregation + formatting + comparison + reporting,
        "preparation": preparation,
        "ingestion":   ingestion,
        "cleaning":    cleaning,
        "validation":  validation,
        "aggregation": aggregation,
        "comparison":  comparison,
        "formatting":  formatting,
        "reporting":   reporting,
        "silver":      ingestion + cleaning,
        "f0":          preparation,
        "f1":          ingestion,
        "f2":          cleaning,
        "f3":          validation,
        "f4":          aggregation,
        "f5":          comparison,
        "f6":          formatting,
        "f7":          reporting,
    }
