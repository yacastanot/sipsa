"""POST /procesar/{mes} — dispara la ejecución del pipeline Kedro."""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sipsa_ipc.api.auth import limiter, require_api_key
from sipsa_ipc.api.data_store import parse_periodo, store
from sipsa_ipc.api.models import PipelineStatus

log = logging.getLogger(__name__)

router = APIRouter(prefix="/procesar", tags=["Pipeline"])

_PROJECT_ROOT = Path(__file__).parents[4]
_KEDRO_EXE = _PROJECT_ROOT / ".venv" / "Scripts" / "kedro.exe"


@router.post(
    "/{mes}",
    response_model=PipelineStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ejecutar pipeline Kedro para un período",
    description=(
        "Lanza `kedro run` de forma síncrona para el período indicado. "
        "El parámetro `mes` debe tener el formato `NombreMesAAAA` (ej.: `Abril2025`). "
        "La API actualiza su caché en memoria tras la ejecución exitosa. "
        "**Requiere que el archivo de entrada ya esté en `data/01_raw/`**."
    ),
)
@limiter.limit("5/minute")
async def ejecutar_pipeline(
    request: Request,
    mes: str,
    _key: str = Depends(require_api_key),
) -> PipelineStatus:
    try:
        mes_nombre, anio = parse_periodo(mes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    kedro_bin = str(_KEDRO_EXE) if _KEDRO_EXE.exists() else "kedro"

    log.info("Disparando kedro run para período %s %d", mes_nombre, anio)
    try:
        result = subprocess.run(
            [kedro_bin, "run"],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="kedro no encontrado. Verifica que el .venv esté configurado.",
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="El pipeline superó el límite de 10 minutos.",
        )

    if result.returncode != 0:
        log.error("kedro run falló | rc=%d | stderr=%s", result.returncode, result.stderr[:500])
        return PipelineStatus(
            mes=mes,
            estado="error",
            mensaje=result.stderr[:500] if result.stderr else "Error desconocido.",
            returncode=result.returncode,
        )

    store.load()
    log.info("Pipeline completado y caché recargada para %s", mes)
    return PipelineStatus(
        mes=mes,
        estado="completado",
        mensaje=f"Pipeline ejecutado correctamente para {mes_nombre} {anio}.",
        returncode=0,
    )
