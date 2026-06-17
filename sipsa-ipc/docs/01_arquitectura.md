# Arquitectura — SIPSA-Abastecimiento

**Stack:** Python 3.13 · Kedro 0.19.15 · pandas 2.3 · FastAPI 0.115 · openpyxl 3.1  
**Origen:** Migración de `SIPSA_A_MODELO_IPC.sas` (≈600 líneas SAS) + macros VBA

---

## Visión general

El proceso toma el snapshot mensual de cantidades del Sistema SIPSA y produce:

- **T38** `SIPSA_IPC_YYYYMMDD.xlsx` — 5 hojas de datos compatibles con `FORMATO_SIPSA_IPC.xlsm`.
- **T39** `Alimentos_priorizados_*.xlsx` — estructura idéntica al output del macro VBA "PEGAR DATOS".
- **T40** `historico_td_total.parquet` — acumulado mensual para análisis de tendencia.

El pipeline es reproducible (mismos datos → mismo resultado), versionable en Git y verificable
(277 pruebas automáticas confirman equivalencia bit a bit con SAS).

---

## Estructura del proyecto

```
SIPSA-Abastecimiento/
├── conf/base/
│   ├── catalog.yml                  # Datasets Kedro (rutas de entrada/salida)
│   ├── parameters.yml               # Parámetros mensuales (mes, año, archivo)
│   ├── parameters_articulos_ipc.yml # Tabla maestra correlativa IPC ↔ SIPSA
│   └── logging.yml
├── data/
│   ├── 01_raw/          # Excel de entrada (copiar aquí cada mes)
│   ├── 02_intermediate/ # base_sipsa_bronze.parquet
│   ├── 03_primary/      # base_sipsa_clean.parquet, base_ipc_filtrada.parquet
│   ├── 04_feature/      # td_total*.parquet, td_abast*.parquet, historico_td_total.parquet
│   └── 08_reporting/    # T38, T39, COBERTURA.xlsx, No_mapeados_IPC.xlsx
├── src/sipsa_abastecimiento/
│   ├── pipelines/       # F0–F7 (ver sección siguiente)
│   ├── validations/     # Esquemas pandera
│   └── pipeline_registry.py
├── app.py               # Interfaz web FastAPI (UI + ejecución de pipelines)
├── templates/           # HTML de la interfaz web
├── tests/               # unit · integration
├── docs/
└── scripts/             # .bat para Windows
```

---

## Pipelines Kedro

`kedro run` ejecuta F0 → F1 → F2 → F3 → F4 → F6 → F5 → F7 en ese orden.
Cada fase se puede ejecutar sola con `kedro run --pipeline f<N>`.

```
Excel mensual (BASE SIPSA_A + Artículos_IPC + Alimentos IPC Vs SIPSA_A)
    │
    ▼
[F0 preparation] ──► articulos_ipc_actualizado (MemoryDataset)
    │                  Valida los 3 períodos (t, t-1, t-12)
    │                  Asigna códigos 1001…1029 en orden alfabético
    │                  Construye mapeo variedades SIPSA → artículo IPC
    ▼
[F1 ingestion] ──────► base_sipsa_bronze.parquet (02_intermediate)
    │                  Lee hoja "BASE SIPSA_A" con dtype forzado
    │                  Valida schema con pandera (lazy=True)
    ▼
[F2 cleaning] ───────► base_sipsa_clean.parquet (03_primary)
    │                  Strip/compacta texto · normaliza fechas
    │                  Parsea Fuente → Ciudad + Central
    │                  Asigna PerFecha (Mes actual/anterior/Año anterior)
    │                  Convierte Cant Kg → Cant_Ton · mapea variedades → RArtículo_IPC
    ▼
[F3 validation] ─────► base_ipc_filtrada.parquet (03_primary)
    │                  No_mapeados_IPC.xlsx · COBERTURA.xlsx
    │                  Retiene solo canasta IPC (RArtículo_IPC ≠ NaN)
    │                  Genera reportes de calidad
    ▼
[F4 aggregation] ────► td_total.parquet · td_abast.parquet
    │                  td_destino.parquet · td_abast_otros.parquet
    │                  PROC MEANS equivalente: SUM(Cant_Ton) por artículo × período/dimensión
    │                  Calcula Participación% por artículo
    ▼
[F6 formatting] ─────► td_abast_fmt · td_destino_fmt · td_abast_otros_fmt
    │                  PropCase en departamentos y países
    │                  Correcciones post-PropCase ("Valle del Cauca", "Norte de Santander")
    │                  Ordena por RArtículo_IPC ASC, Participación DESC
    ▼
[F5 comparison] ─────► td_total_variaciones.parquet (04_feature)
    │                  VariacMensual y VariacAnual con formato SAS BEST12.
    │                  Coma decimal colombiana · verificado bit a bit vs SAS
    ▼
[F7 reporting] ──────► SIPSA_IPC_YYYYMMDD.xlsx (T38, 5 hojas)
                       Alimentos_priorizados_*.xlsx (T39, 1 hoja)
                       historico_td_total.parquet (T40)
```

---

## Catálogo de datos

Todos los Parquets usan `kedro_datasets.pandas.ParquetDataset` con compresión `snappy`.
Los Excel de salida se escriben directamente con `openpyxl` desde los nodos (no con
`ExcelDataset` del catálogo — ver Decisión 1 abajo).

| Dataset | Tipo | Capa | Filas típicas |
|---------|------|------|---------------|
| `base_sipsa_bronze` | Parquet | 02_intermediate | ~547 K |
| `base_sipsa_clean` | Parquet | 03_primary | ~547 K |
| `base_ipc_filtrada` | Parquet | 03_primary | ~327 K |
| `td_total` | Parquet | 04_feature | 29 |
| `td_abast` | Parquet | 04_feature | ~500 |
| `td_destino` | Parquet | 04_feature | ~500 |
| `td_abast_otros` | Parquet | 04_feature | ~30 |
| `td_total_variaciones` | Parquet | 04_feature | 29 |
| `td_abast_fmt` | Parquet | 04_feature | ~500 |
| `td_destino_fmt` | Parquet | 04_feature | ~500 |
| `td_abast_otros_fmt` | Parquet | 04_feature | ~30 |
| `historico_td_total` | Parquet | 04_feature | crece +29/mes |

---

## Decisiones de diseño

| Decisión | Alternativa descartada | Razón |
|----------|----------------------|-------|
| Leer Excel en nodo, no en catálogo | `ExcelDataset` + `${params:archivo}` | OmegaConf no soporta interpolación en rutas de datasets en Kedro 0.19 |
| Parquet Snappy para intermedios | CSV | Tipado estricto, 5× más rápido de leer, 80% menos espacio |
| Códigos IPC calculados fresh cada mes | Hardcodeados en YAML | Los artículos de la canasta cambian mensualmente; recalcular evita deuda de mantenimiento |
| BEST12. con anchura de columna | `:.12g` (12 dígitos significativos) | SAS BEST12. cuenta columnas de ancho, no dígitos significativos; los ceros fractales consumen ancho sin ser dígitos |
| pandera `lazy=True` | `lazy=False` (fallo en primer error) | Expone todas las violaciones del Excel de una sola vez, facilitando la corrección del origen |

---

## Pruebas

```cmd
.venv\Scripts\pytest.exe tests\ -m "not slow" -q    # 277 pruebas, ~20 s
.venv\Scripts\pytest.exe tests\ -m slow              # E2E (requiere Excel de entrada)
```

| Suite | Ruta | Qué verifica |
|-------|------|-------------|
| Unitarias pipeline | `tests/pipelines/*/test_nodes.py` | Cada nodo individualmente con datos sintéticos |
| Integración numérica | `tests/integration/test_numeric_vs_sas.py` | Diferencia = 0.0 vs SAS para los 29 artículos |
| Integración artefactos | `tests/integration/test_pipeline_e2e.py` | Shape y esquema de los Parquets de salida |
