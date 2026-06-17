"""API FastAPI — SIPSA IPC.

Inicio rápido (desde la carpeta sipsa-ipc/):
    uvicorn sipsa_ipc.api.main:app --reload

Swagger UI:   http://localhost:8000/docs
ReDoc:        http://localhost:8000/redoc
OpenAPI JSON: http://localhost:8000/openapi.json

Autenticación:
    Header X-API-Key con el valor de la variable de entorno SIPSA_API_KEY.
    Por defecto en desarrollo: "dev-key-sipsa".

Ejemplo de petición:
    curl -H "X-API-Key: dev-key-sipsa" http://localhost:8000/meses
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from sipsa_ipc.api.auth import limiter
from sipsa_ipc.api.data_store import store
from sipsa_ipc.api.routers import (
    abastecimiento,
    comparacion,
    estadisticas,
    meses,
    pipeline,
)

_DESCRIPTION = """
## API SIPSA IPC

Expone los resultados del pipeline de procesamiento mensual del Sistema de
Información de Precios y Abastecimiento del Sector Agropecuario (**SIPSA**)
para los **29 artículos de la canasta IPC** de Colombia.

### Endpoints disponibles

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/meses` | Períodos disponibles en el histórico |
| GET | `/abastecimiento/{mes}/{articulo}` | Procedencia por departamento |
| GET | `/abastecimiento/destinos/{mes}/{articulo}` | Distribución por ciudad destino |
| GET | `/estadisticas/{articulo}/{mes}` | Variaciones + resumen de abastecimiento |
| GET | `/comparacion/{periodo_a}/{periodo_b}` | Comparación entre dos períodos |
| POST | `/procesar/{mes}` | Ejecutar pipeline Kedro (requiere datos en disco) |

### Autenticación
Todas las rutas requieren el header `X-API-Key`.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="SIPSA IPC API",
    description=_DESCRIPTION,
    version="1.0.0",
    contact={"name": "DANE — Dirección de Metodología y Producción Estadística"},
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)

app.include_router(meses.router)
app.include_router(abastecimiento.router)
app.include_router(estadisticas.router)
app.include_router(comparacion.router)
app.include_router(pipeline.router)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "api": "SIPSA IPC",
        "version": "1.0.0",
        "estado": "activo",
    }


@app.get("/health", tags=["Sistema"], summary="Estado del servicio")
async def health():
    return {
        "estado": "ok",
        "datos_cargados": store.loaded,
        "articulos_disponibles": len(store.todos_los_codigos()),
        "periodos_disponibles": len(store.periodos_disponibles()),
    }
