"""GET /comparacion/{periodo_a}/{periodo_b} — variaciones entre dos períodos."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sipsa_ipc.api.auth import limiter, require_api_key
from sipsa_ipc.api.data_store import parse_periodo, store
from sipsa_ipc.api.models import ComparacionItem, ComparacionResponse

router = APIRouter(prefix="/comparacion", tags=["Comparación"])


@router.get(
    "/{periodo_a}/{periodo_b}",
    response_model=ComparacionResponse,
    summary="Variaciones entre dos períodos",
    description=(
        "Compara el abastecimiento total de los 29 artículos IPC entre dos "
        "períodos disponibles en el histórico. "
        "Formato de período: `NombreMesAAAA` (ej.: `Abril2025`). "
        "La variación se calcula como `(periodo_a - periodo_b) / periodo_b * 100`."
    ),
)
@limiter.limit("60/minute")
async def comparar_periodos(
    request: Request,
    periodo_a: str,
    periodo_b: str,
    _key: str = Depends(require_api_key),
) -> ComparacionResponse:
    try:
        mes_a, anio_a = parse_periodo(periodo_a)
        mes_b, anio_b = parse_periodo(periodo_b)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    df_a = store.historico_periodo(mes_a, anio_a)
    df_b = store.historico_periodo(mes_b, anio_b)

    if df_a.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Período '{periodo_a}' no disponible en el histórico.",
        )
    if df_b.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Período '{periodo_b}' no disponible en el histórico.",
        )

    merged = df_a[["RArtículo_IPC", "Artículo_IPC", "AbastTotal_MesActual"]].merge(
        df_b[["RArtículo_IPC", "AbastTotal_MesActual"]],
        on="RArtículo_IPC",
        suffixes=("_a", "_b"),
    )

    items: list[ComparacionItem] = []
    for _, row in merged.sort_values("RArtículo_IPC").iterrows():
        val_a = float(row["AbastTotal_MesActual_a"])
        val_b = float(row["AbastTotal_MesActual_b"])
        variacion = (val_a - val_b) / val_b * 100 if val_b != 0 else 0.0
        items.append(
            ComparacionItem(
                articulo_ipc=str(row["Artículo_IPC"]),
                codigo_ipc=int(row["RArtículo_IPC"]),
                abast_periodo_a=val_a,
                abast_periodo_b=val_b,
                variacion_pct=round(variacion, 6),
            )
        )

    return ComparacionResponse(
        periodo_a=periodo_a,
        periodo_b=periodo_b,
        articulos=items,
    )
