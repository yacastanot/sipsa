"""GET /abastecimiento/{mes}/{articulo} — procedencia por departamento."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sipsa_ipc.api.auth import limiter, require_api_key
from sipsa_ipc.api.data_store import store
from sipsa_ipc.api.models import AbastecimientoResponse, AbastItem, DestinoResponse, DestinoItem

router = APIRouter(prefix="/abastecimiento", tags=["Abastecimiento"])


def _resolve_codigo(articulo: str) -> int:
    """Acepta código numérico (1001-1029) o nombre (ARROZ, arroz)."""
    if articulo.isdigit():
        return int(articulo)
    codigos = store.todos_los_codigos()
    nombre_norm = articulo.upper().strip()
    for c in codigos:
        nombre = store.articulo_nombre(c)
        if nombre and nombre.upper() == nombre_norm:
            return c
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Artículo no encontrado: '{articulo}'. "
               f"Usa el código IPC (1001–1029) o el nombre exacto.",
    )


@router.get(
    "/{mes}/{articulo}",
    response_model=AbastecimientoResponse,
    summary="Procedencia por departamento",
    description=(
        "Retorna las toneladas abastecidas y participación % por departamento "
        "para un artículo IPC en el período indicado. "
        "`mes` = `NombreMesAAAA` (ej.: `Abril2025`). "
        "`articulo` = código IPC (1001–1029) o nombre del artículo."
    ),
)
@limiter.limit("60/minute")
async def abastecimiento_departamento(
    request: Request,
    mes: str,
    articulo: str,
    _key: str = Depends(require_api_key),
) -> AbastecimientoResponse:
    # Validamos el período (por ahora solo verificamos formato; en el futuro se filtrará por mes)
    from sipsa_ipc.api.data_store import parse_periodo
    try:
        parse_periodo(mes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    codigo = _resolve_codigo(articulo)
    nombre = store.articulo_nombre(codigo)
    if nombre is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Código {codigo} no encontrado.")

    df = store.abastecimiento_por_articulo(codigo)
    if df.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sin datos de abastecimiento.")

    total = float(df["Total_Artículo"].iloc[0]) if "Total_Artículo" in df.columns else float(df["Sum_Ton"].sum())
    items = [
        AbastItem(
            departamento=str(row["Departamento Proc."]),
            sum_ton=float(row["Sum_Ton"]),
            participacion_pct=float(row["Participación"]),
        )
        for _, row in df.sort_values("Participación", ascending=False).iterrows()
    ]
    return AbastecimientoResponse(
        periodo=mes,
        articulo_ipc=nombre,
        codigo_ipc=codigo,
        total_ton=total,
        departamentos=items,
    )


@router.get(
    "/destinos/{mes}/{articulo}",
    response_model=DestinoResponse,
    summary="Distribución por ciudad destino",
    description=(
        "Retorna las toneladas y participación % por ciudad de destino "
        "para un artículo IPC."
    ),
)
@limiter.limit("60/minute")
async def abastecimiento_destinos(
    request: Request,
    mes: str,
    articulo: str,
    _key: str = Depends(require_api_key),
) -> DestinoResponse:
    from sipsa_ipc.api.data_store import parse_periodo
    try:
        parse_periodo(mes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    codigo = _resolve_codigo(articulo)
    nombre = store.articulo_nombre(codigo)
    if nombre is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Código {codigo} no encontrado.")

    df = store.destinos_articulo(codigo)
    if df.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sin datos de destino.")

    total = float(df["Total_Artículo"].iloc[0])
    items = [
        DestinoItem(
            ciudad=str(row["Ciudad"]),
            sum_ton=float(row["Sum_Ton"]),
            participacion_pct=float(row["Participación"]),
        )
        for _, row in df.sort_values("Participación", ascending=False).iterrows()
    ]
    return DestinoResponse(
        periodo=mes,
        articulo_ipc=nombre,
        codigo_ipc=codigo,
        total_ton=total,
        ciudades=items,
    )
