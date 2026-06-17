# Módulos — SIPSA IPC

Un bloque por archivo de `src/sipsa_ipc/`. Para cada módulo: propósito,
función principal, entradas/salidas y ejemplo de llamada entre módulos.

---

## `pipeline_registry.py`

Registra todos los pipelines Kedro del proyecto.

```python
from kedro.framework.project import pipelines
# kedro run                 → ejecuta __default__ (F0+F1+F2+F3+F4+F6+F5+F7)
# kedro run --pipeline f2   → solo limpieza
# kedro run --pipeline silver → F1+F2 (ingesta y limpieza)
```

| Alias | Pipelines incluidos |
|-------|-------------------|
| `__default__` | F0 + F1 + F2 + F3 + F4 + F6 + F5 + F7 |
| `f0` | preparation |
| `f1` | ingestion |
| `f2` | cleaning |
| `f3` | validation |
| `f4` | aggregation |
| `f5` | comparison |
| `f6` | formatting |
| `f7` | reporting |
| `silver` | F1 + F2 |

---

## `validations/schemas.py`

Esquema pandera para validar la capa Bronze (salida de F1).

**`SCHEMA_RAW`** — valida 6 columnas requeridas:

| Columna | Tipo | Regla |
|---------|------|-------|
| `Fuente` | str | no nulo |
| `FechaEncuesta` | datetime64 | no nulo |
| `Ali` | str | no nulo |
| `Cant Kg` | float | >= 0, nullable |
| `Departamento Proc.` | str | no nulo |
| `Municipio Proc.` | str | no nulo |

Validación con `lazy=True`: expone todas las violaciones de una vez en lugar de
fallar en la primera.

---

## `pipelines/preparation/nodes.py`

**Función principal:** `preparar_articulos_ipc()`

Valida el archivo de entrada y construye la configuración IPC del mes.

- [1/4] Verifica que los 3 períodos (t, t-1, t-12) estén en `FechaEncuesta`.
- [3/4] Compara artículos en "Artículos_IPC" vs "Alimentos IPC Vs SIPSA_A" (advertencias).
- [4/4] Asigna códigos 1001…N en orden alfabético y construye mapeo variedades → artículo.

```python
config = preparar_articulos_ipc(
    archivo_entrada="data/01_raw/Alimentos priorizados may2026_SIPSA.xlsx",
    mes_actual_nombre="Mayo",
    mes_anterior_nombre="Abril",
    anio_actual=2026,
    anio_anterior=2025,
    articulos_ipc={"correlativa": {...}},
)
# config = {"variedades": {"Aguacate Hass": "AGUACATE", ...}, "codigos": {"AGUACATE": 1001, ...}}
```

---

## `pipelines/ingestion/nodes.py`

**Función principal:** `leer_base()`

Lee la hoja "BASE SIPSA_A" del Excel mensual con tipos forzados, normaliza nombres
de columna con variantes históricas y valida con `SCHEMA_RAW`.

```python
df_bronze = leer_base("data/01_raw/Alimentos priorizados may2026_SIPSA.xlsx")
# → DataFrame ~547K filas, 18 columnas, 3 períodos embebidos
```

**Helpers privados:**
- `_normalizar_columnas()` — renombra variantes de encabezados de distintas versiones del Excel.
- `_verificar_columnas()` — lanza `ValueError` con mensaje claro si faltan columnas requeridas.

---

## `pipelines/cleaning/nodes.py`

**Función principal:** `limpiar_base()`

Transforma el Bronze en la capa Clean. Aplica 8 pasos en secuencia:

| Paso | Función privada | Qué hace |
|------|----------------|---------|
| 1 | `_estandarizar_texto()` | Strip y compacta espacios en 14 columnas de texto |
| 2 | `_rellenar_otros()` | Vacíos/NA en Departamento/Municipio → "OTRO" |
| 3 | `_normalizar_fechas()` | `FechaEncuesta` → datetime64 |
| 4 | `_limpiar_divipola()` | Elimina comillas y espacios de códigos DIVIPOLA |
| 5 | `_crear_ciudad_y_central()` | Parsea `Fuente = "Ciudad, Central"` con replacements |
| 6 | `_crear_periodo()` | Asigna `PerFecha` según fechas vs parámetros del mes |
| 7 | `_crear_cantidad_toneladas()` | `Cant Kg ÷ 1000 → Cant_Ton` |
| 8 | `_mapear_articulos_ipc()` | `Ali → Artículo_IPC → RArtículo_IPC` (código Int64) |

---

## `pipelines/validation/nodes.py`

Tres nodos de validación de calidad:

| Función | Entrada | Salida |
|---------|---------|--------|
| `filtrar_articulos_canasta()` | `base_sipsa_clean` | `base_ipc_filtrada` (~327K filas, solo canasta IPC) |
| `generar_no_mapeados()` | `base_sipsa_clean` | `no_mapeados_ipc` (variedades SIPSA sin mapeo IPC) |
| `calcular_cobertura()` | `base_ipc_filtrada` | `cobertura_ipc` (29 artículos: N registros Mes actual) |

---

## `pipelines/aggregation/nodes.py`

Cuatro funciones de agregación (equivalente a `PROC MEANS` de SAS):

| Función | Salida | Dimensión |
|---------|--------|-----------|
| `calcular_td_total()` | `td_total` | Artículo × 3 períodos (29 filas) |
| `calcular_td_abast()` | `td_abast` | Artículo × Departamento origen (Mes actual) |
| `calcular_td_destino()` | `td_destino` | Artículo × Ciudad destino (Mes actual) |
| `calcular_td_abast_otros()` | `td_abast_otros` | Artículo × País importación (Mes actual, puede estar vacío) |

Todas calculan `Participación% = (Sum_Ton / Total_Artículo) × 100`.

---

## `pipelines/comparison/nodes.py`

**Función principal:** `calcular_variaciones()`

Agrega `VariacMensual` y `VariacAnual` a `td_total` con formato SAS BEST12.:
- Ancho máximo 12 caracteres (signo + enteros + coma decimal + decimales).
- Coma decimal colombiana (`,` en lugar de `.`).
- Sufijo `%`.

```
-3.15987491238  →  "-3,159874912%"
7.96708264345   →  "7,9670826435%"
```

También conserva `VariacMensual_num` y `VariacAnual_num` (float) para cálculos
posteriores en F7.

---

## `pipelines/formatting/nodes.py`

Tres funciones de formateo visual (equivalente a `propcase()` + `PROC SORT` de SAS):

| Función | Transformación |
|---------|---------------|
| `formatear_td_abast()` | PropCase en Departamento + 2 correcciones + orden |
| `formatear_td_destino()` | Orden por artículo + participación (Ciudad ya correcta desde F2) |
| `formatear_td_abast_otros()` | PropCase en Municipio (nombres de países) + 1 corrección + orden |

Correcciones post-PropCase:
- `"Valle Del Cauca"` → `"Valle del Cauca"`
- `"Norte De Santander"` → `"Norte de Santander"`
- `"Estados Unidos De América"` → `"Estados Unidos de América"`

---

## `pipelines/reporting/nodes.py`

Tres nodos de exportación final:

**`exportar_sipsa_ipc()`** — genera T38 `SIPSA_IPC_YYYYMMDD.xlsx` con 5 hojas.
La hoja TD_Abast incluye `Descr_pegar` (col 9) y TD_Destino incluye `Descr_pegar` (col 8)
para que el macro VBA "PEGAR DATOS" de `FORMATO_SIPSA_IPC.xlsm` pueda hacer `VLookup`.

**`exportar_alimentos_priorizados()`** — genera T39 `Alimentos_priorizados_*.xlsx`.
Carga la plantilla "Artículos_IPC" del Excel de entrada (si existe), rellena las
columnas dinámicas I, K, L–P y aplica formato visual idéntico al archivo de referencia.

**`guardar_historico()`** — agrega el mes actual al Parquet acumulado `historico_td_total`.

---

## `app.py` (raíz del proyecto)

Interfaz web FastAPI. Sirve la UI y orquesta la ejecución del pipeline.

```
GET  /                  → interfaz web (auth HTTP Basic requerida)
POST /upload            → sube Excel a data/01_raw/ y actualiza parameters.yml
POST /configure         → actualiza mes/año en parameters.yml
POST /run               → lanza kedro run con streaming de logs (SSE)
GET  /outputs           → lista archivos .xlsx en data/08_reporting/
GET  /download/{file}   → descarga archivo de reporting
DELETE /outputs         → limpia archivos generados
```

Credenciales configuradas en `.env` con `SIPSA_IPC_USER` / `SIPSA_IPC_PASS`.
