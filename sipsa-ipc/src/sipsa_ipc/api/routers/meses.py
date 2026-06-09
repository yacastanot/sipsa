"""GET /meses — lista los períodos disponibles en el histórico."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from sipsa_ipc.api.auth import limiter, require_api_key
from sipsa_ipc.api.data_store import store
from sipsa_ipc.api.models import ListaMesesResponse, MesDisponible

router = APIRouter(prefix="/meses", tags=["Períodos"])


@router.get(
    "",
    response_model=ListaMesesResponse,
    summary="Listar períodos disponibles",
    description=(
        "Retorna todos los meses procesados y disponibles en el histórico. "
        "Cada período se puede usar como parámetro `{mes}` en los demás endpoints "
        "con el formato `NombreMesAAAA` (ej.: `Abril2025`)."
    ),
)
@limiter.limit("60/minute")
async def listar_meses(
    request: Request,
    _key: str = Depends(require_api_key),
) -> ListaMesesResponse:
    registros = store.periodos_disponibles()
    periodos = [
        MesDisponible(mes=r["mes"], anio=int(r["anio"]), periodo=r["periodo"])
        for r in registros
    ]
    return ListaMesesResponse(periodos=periodos, total=len(periodos))
