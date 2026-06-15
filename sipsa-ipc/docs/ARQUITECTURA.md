> **Este archivo se reemplazó por [01_arquitectura.md](01_arquitectura.md).**

# Arquitectura Técnica — SIPSA IPC Python/Kedro

**Proyecto:** Migración SIPSA_A_MODELO_IPC.sas → Python + Kedro + FastAPI  
**Versión:** 1.0.0  
**Fecha:** Junio 2026  
**Stack:** Python 3.13 · Kedro 0.19.15 · pandas 2.3 · FastAPI 0.115 · openpyxl 3.1

---

## 1. Visión general

El proceso SIPSA IPC toma el snapshot mensual de precios y cantidades del Sistema de
Información de Precios y Abastecimiento del Sector Agropecuario (SIPSA) y produce las
tablas de abastecimiento que alimentan el cálculo del Índice de Precios al Consumidor
(IPC) del DANE.

La migración reemplaza el programa SAS `SIPSA_A_MODELO_IPC.sas` (≈600 líneas) y las
macros auxiliares por un pipeline Python estructurado en Kedro que es:

- **Reproducible**: cualquier ejecución con los mismos datos produce el mismo resultado.
- **Versionable**: todo el código vive en Git; los datos intermedios en `data/`.
- **Verificable**: 277 pruebas automáticas validan la equivalencia bit a bit con SAS.
- **Consultable**: API REST expone los datos procesados sin necesidad de abrir Excel.

---

## 2. Estructura del proyecto

```
sipsa-ipc/
├── conf/base/
│   ├── catalog.yml                  # DataSets Kedro (rutas de entrada/salida)
│   ├── parameters.yml               # Parámetros mensuales (mes, año, archivo)
│   ├── parameters_articulos_ipc.yml # Mapeo artículo IPC → código RArtículo_IPC
│   └── logging.yml
├── data/
│   ├── 01_raw/          # Excel de entrada (Base_SIPSA_IPC_mmmAAAA.xlsx)
│   ├── 02_intermediate/ # base_sipsa_bronze.parquet
│   ├── 03_primary/      # base_sipsa_clean.parquet, base_ipc_filtrada.parquet
│   ├── 04_feature/      # td_total*.parquet, td_abast*.parquet, historico_td_total.parquet
│   └── 08_reporting/    # SIPSA_IPC_YYYYMMDD.xlsx, Alimentos_priorizados_*.xlsx,
│                        # COBERTURA.xlsx, No_mapeados_IPC.xlsx
├── src/sipsa_ipc/
│   ├── pipelines/       # 7 pipelines Kedro (ver sección 3)
│   ├── api/             # API REST FastAPI (ver sección 5)
│   ├── validations/     # Esquemas pandera
│   └── pipeline_registry.py
├── tests/               # 277 pruebas (unit, integration, performance)
├── docs/                # Esta documentación
└── scripts/             # Scripts auxiliares Windows (.bat)
```

---

## 3. Pipelines Kedro

El pipeline completo (`kedro run`) encadena 7 sub-pipelines en orden.
Cada uno se puede ejecutar de forma independiente con `kedro run --pipeline <nombre>`.

```
Excel entrada
    │
    ▼
[F1] ingestion ──► base_sipsa_bronze.parquet (02_intermediate)
    │
    ▼
[F2] cleaning ───► base_sipsa_clean.parquet  (03_primary)
    │
    ▼
[F3] validation ─► base_ipc_filtrada.parquet (03_primary)
                   No_mapeados_IPC.xlsx
                   COBERTURA.xlsx
    │
    ▼
[F4] aggregation ► td_total.parquet          (04_feature)
                   td_abast.parquet
                   td_destino.parquet
                   td_abast_otros.parquet
    │
    ▼
[F5] comparison ─► td_total_variaciones.parquet (04_feature)
    │
    ▼
[F6] formatting ─► td_abast_fmt.parquet      (04_feature)
                   td_destino_fmt.parquet
                   td_abast_otros_fmt.parquet
    │
    ▼
[F7] reporting ──► SIPSA_IPC_YYYYMMDD.xlsx   (08_reporting)
                   Alimentos_priorizados_*.xlsx
                   historico_td_total.parquet (04_feature)
```

### 3.1 F1 — Ingestion

| Nodo | Función | Entrada | Salida |
|------|---------|---------|--------|
| leer_base | `leer_base()` | Excel mensual (`params:archivo_entrada`) | `base_sipsa_bronze` |

- Lee el Excel con `openpyxl`, inferencia de tipos, encoding Latin-1.
- Valida esquema con **pandera**: columnas `Fuente`, `FechaEncuesta`, `Ali`, `Cant Kg`, `Grupo`.
- Persiste ~547K filas como Parquet (≈20 MB, vs ≈120 MB del Excel).

### 3.2 F2 — Cleaning

| Nodo | Función | Entrada | Salida |
|------|---------|---------|--------|
| limpiar_base | `limpiar_base()` | bronze | `base_sipsa_clean` |

Equivalente al Data Step inicial de SAS. Operaciones clave:
- Convierte `Cant Kg` → `Cant_Ton` (÷ 1 000).
- Mapea `Fuente` → `Ciudad` y `Central` (tabla fuentes).
- Asigna `PerFecha` = "Mes actual" / "Mes anterior" / "Año anterior" según `FechaEncuesta`.
- Mapea artículos SIPSA → `Artículo_IPC` y `RArtículo_IPC` (código 1001–1029).

### 3.3 F3 — Validation

| Nodo | Función | Entrada | Salida |
|------|---------|---------|--------|
| filtrar_articulos_canasta | `filtrar_articulos_canasta()` | clean | `base_ipc_filtrada` |
| generar_no_mapeados | `generar_no_mapeados()` | clean | `No_mapeados_IPC.xlsx` |
| calcular_cobertura | `calcular_cobertura()` | filtrada | `COBERTURA.xlsx` |

- Retiene solo filas con `RArtículo_IPC` ≠ NaN (canasta IPC).
- Resultado típico: ~327K filas de ~547K originales.
- `COBERTURA.xlsx`: reporte de 29 artículos cubiertos vs. esperados.

### 3.4 F4 — Aggregation

Genera las 4 tablas maestras replicando los `PROC MEANS` de SAS:

| Tabla | Descripción | Filas típicas |
|-------|-------------|---------------|
| `td_total` | Toneladas totales por artículo × 3 períodos | 29 |
| `td_abast` | Toneladas por artículo × departamento origen (Mes actual) | ~500 |
| `td_destino` | Toneladas por artículo × ciudad destino (Mes actual) | ~500 |
| `td_abast_otros` | Importaciones por artículo × municipio origen (Mes actual) | ~30 |

### 3.5 F5 — Comparison

| Nodo | Función | Entrada | Salida |
|------|---------|---------|--------|
| calcular_variaciones | `calcular_variaciones()` | td_total | `td_total_variaciones` |

Calcula variación mensual y anual porcentual y las formatea en estilo SAS BEST12.:
```
VariacMensual = (MesActual - MesAnterior) / MesAnterior × 100
VariacAnual   = (MesActual - AnoAnterior)  / AnoAnterior × 100
```
El formato BEST12. ocupa exactamente 12 columnas (signo + enteros + coma + decimales).
Verificado bit a bit contra SAS: 0 diferencias en todos los 29 artículos.

### 3.6 F6 — Formatting

Aplica PropCase (Primera Letra Mayúscula) a departamentos y países, y ordena por
Participación descendente. Equivale al `PROC SORT` + `propcase()` de SAS.

### 3.7 F7 — Reporting

| Nodo | Función | Salidas |
|------|---------|---------|
| exportar_sipsa_ipc | 4 hojas Excel formateadas | `SIPSA_IPC_YYYYMMDD.xlsx` |
| exportar_alimentos_priorizados | Resumen por grupo | `Alimentos_priorizados_*.xlsx` |
| guardar_historico | Acumula meses anteriores | `historico_td_total.parquet` |

El Excel principal `SIPSA_IPC_YYYYMMDD.xlsx` contiene las hojas:
`TD_Total`, `TD_Abast`, `TD_Destino`, `TD_Abast_Otros`.

---

## 4. Catálogo de datos

Definido en `conf/base/catalog.yml`. Todos los Parquets intermedios usan
`kedro_datasets.pandas.ParquetDataset` con compresión `snappy`.

Los archivos Excel de salida se escriben directamente con `openpyxl` desde el nodo
`exportar_sipsa_ipc` (no se usa `ExcelDataset` del catálogo, para evitar la
limitación de interpolación `${params:...}` en Kedro 0.19.15 con OmegaConf).

---

## 5. API REST (FastAPI)

Expone los datos procesados del mes activo. Se inicia con:

```bat
scripts\iniciar_api.bat
```

o manualmente:

```bash
cd sipsa-ipc
uvicorn sipsa_ipc.api.main:app --host 0.0.0.0 --port 8000
```

La documentación interactiva queda disponible en `http://localhost:8000/docs`.

Autenticación: header `X-API-Key` con valor de la variable de entorno `SIPSA_API_KEY`
(por defecto `dev-key-sipsa` en desarrollo).

### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado de la API |
| GET | `/meses` | Lista de períodos disponibles en el histórico |
| GET | `/abastecimiento/{mes}/{articulo}` | Toneladas por departamento de procedencia |
| GET | `/abastecimiento/destinos/{mes}/{articulo}` | Toneladas por ciudad destino |
| GET | `/estadisticas/{articulo}/{mes}` | Variaciones + top departamentos/destinos |
| GET | `/comparacion/{periodo_a}/{periodo_b}` | Comparación entre dos períodos |
| POST | `/procesar/{mes}` | Ejecuta `kedro run` y recarga la caché |

Ver [MANUAL_API.md](MANUAL_API.md) para ejemplos completos.

---

## 6. Autenticación y seguridad

- **API Key**: valor configurable en `.env` (`SIPSA_API_KEY=<clave>`).
- **Rate limiting**: 60 req/min en endpoints de datos, 5 req/min en `/procesar`.
- **CORS**: configurable; en producción restringir a los hosts DANE permitidos.
- El archivo `.env` nunca se sube a Git (listado en `.gitignore`).

---

## 7. Pruebas

```bash
cd sipsa-ipc
.venv\Scripts\pytest.exe tests\ -m "not slow"   # 277 pruebas (~20 s)
.venv\Scripts\pytest.exe tests\ -m slow          # E2E (requiere Excel de entrada)
```

| Suite | Archivo | Cobertura |
|-------|---------|-----------|
| Unitarias pipeline | `tests/pipelines/*/test_nodes.py` | Cada nodo individualmente |
| API | `tests/api/test_endpoints.py` | 20 pruebas con mocks |
| Integración numérica | `tests/integration/test_numeric_vs_sas.py` | Comparación bit a bit vs SAS |
| Integración artefactos | `tests/integration/test_pipeline_e2e.py` | Existencia y shape de Parquets |
| Rendimiento | `tests/performance/test_api_performance.py` | p99 < 500 ms, 29 artículos concurrentes |

---

## 8. Parámetros mensuales

Al inicio de cada mes actualizar `conf/base/parameters.yml`:

```yaml
mes_actual_nombre:    "Mayo"         # Nombre del mes actual
mes_anterior_nombre:  "Abril"        # Mes anterior
anio_actual:          2025
anio_anterior:        2024
fecha_proceso:        "20250603"     # YYYYMMDD
archivo_entrada:      "data/01_raw/Base_SIPSA_IPC_may2025.xlsx"
```

Luego copiar el Excel de entrada a `data/01_raw/` y ejecutar `kedro run`.

---

## 9. Decisiones de diseño relevantes

| Decisión | Alternativa descartada | Razón |
|----------|----------------------|-------|
| Leer Excel en nodo, no en catálogo | `ExcelDataset` + `${params:archivo}` | OmegaConf no soporta interpolación en rutas de datasets en Kedro 0.19 |
| Parquet con Snappy para intermedios | CSV | Tipado estricto, 5× más rápido de leer, 80% menos espacio |
| MemoryDataset para `precios_entrada` | ParquetDataset | No necesita persistir entre runs; evita archivo temporal |
| BEST12. con anchura de columna | `:.12g` (12 dígitos significativos) | SAS BEST12. cuenta columnas, no dígitos sig.; los ceros iniciales en la parte fraccional consumen columnas sin ser dígitos significativos |
| Singleton `DataStore` en la API | Re-leer Parquets en cada request | Latencia p99 < 10 ms para datos en memoria vs > 500 ms leyendo disco |
