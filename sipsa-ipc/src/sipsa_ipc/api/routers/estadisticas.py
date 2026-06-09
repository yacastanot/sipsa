"""GET /estadisticas/{articulo}/{mes} — variaciones y abastecimiento por artículo."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sipsa_ipc.api.auth import limiter, require_api_key
from sipsa_ipc.api.data_store import parse_periodo, store
from sipsa_ipc.api.models import (
    AbastItem,
    DestinoItem,
    EstadisticasResponse,
    OtrosItem,
)

router = APIRouter(prefix="/estadisticas", tags=["Estadísticas"])

_TOP_N = 5


@router.get(
    "/{articulo}/{mes}",
    response_model=EstadisticasResponse,
    summary="Variaciones y abastecimiento por artículo IPC",
    description=(
        "Retorna para un artículo IPC: toneladas de los 3 períodos, "
        "variación mensual y anual (numérica y formato colombiano), "
        "top departamentos abastecedores, top ciudades destino e importaciones."
    ),
)
@limiter.limit("60/minute")
async def estadisticas_articulo(
    request: Request,
    articulo: str,
    mes: str,
    _key: str = Depends(require_api_key),
) -> EstadisticasResponse:
    try:
        parse_periodo(mes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    # Resolver código IPC
    if articulo.isdigit():
        codigo = int(articulo)
    else:
        codigos = store.todos_los_codigos()
        nombre_norm = articulo.upper().strip()
        codigo_encontrado = next(
            (c for c in codigos if store.articulo_nombre(c) and store.articulo_nombre(c).upper() == nombre_norm),
            None,
        )
        if codigo_encontrado is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artículo no encontrado: '{articulo}'.",
            )
        codigo = codigo_encontrado

    row = store.estadisticas_articulo(codigo)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sin datos de variaciones para código {codigo}.",
        )

    df_abast = store.abastecimiento_por_articulo(codigo)
    df_destino = store.destinos_articulo(codigo)
    df_otros = store.importaciones_articulo(codigo)

    top_deptos = [
        AbastItem(
            departamento=str(r["Departamento Proc."]),
            sum_ton=float(r["Sum_Ton"]),
            participacion_pct=float(r["Participación"]),
        )
        for _, r in df_abast.sort_values("Participación", ascending=False).head(_TOP_N).iterrows()
    ] if not df_abast.empty else []

    top_destinos = [
        DestinoItem(
            ciudad=str(r["Ciudad"]),
            sum_ton=float(r["Sum_Ton"]),
            participacion_pct=float(r["Participación"]),
        )
        for _, r in df_destino.sort_values("Participación", ascending=False).head(_TOP_N).iterrows()
    ] if not df_destino.empty else []

    importaciones = [
        OtrosItem(
            pais=str(r["Municipio Proc."]),
            sum_ton=float(r["Sum_Ton"]),
            participacion_pct=float(r["Participación"]),
        )
        for _, r in df_otros.sort_values("Participación", ascending=False).iterrows()
    ] if not df_otros.empty else []

    return EstadisticasResponse(
        periodo=mes,
        articulo_ipc=str(row["Artículo_IPC"]),
        codigo_ipc=int(row["RArtículo_IPC"]),
        abast_mes_actual=float(row["AbastTotal_MesActual"]),
        abast_mes_anterior=float(row["AbastTotal_MesAnterior"]),
        abast_anio_anterior=float(row["AbastTotal_AnoAnterior"]),
        variac_mensual_pct=float(row["VariacMensual_num"]),
        variac_anual_pct=float(row["VariacAnual_num"]),
        variac_mensual_fmt=str(row["VariacMensual"]),
        variac_anual_fmt=str(row["VariacAnual"]),
        top_departamentos=top_deptos,
        top_destinos=top_destinos,
        importaciones=importaciones,
    )
