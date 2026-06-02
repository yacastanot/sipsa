# Documentación técnica — EMCES Registros Administrativos

**Proyecto:** Migración del proceso mensual EMCES — Registros Administrativos (RA)
**Orígenes:** `Fletes-EMCES 2025-12.R`, `Cancilleria-EMCES 2026-01.sas`, `UnirBase F2026_01C2026_01.sas`
**Destino:** Pipeline Python + Kedro
**Última actualización:** 2026-04-20
**Versión verificada:** Fletes Dic-2025 / Cancillería Ene-2026

---

## Tabla de contenidos

1. [Contexto y objetivo](#1-contexto-y-objetivo)
2. [Stack tecnológico](#2-stack-tecnológico)
3. [Estructura del proyecto](#3-estructura-del-proyecto)
4. [Archivos de entrada](#4-archivos-de-entrada)
5. [Parámetros mensuales](#5-parámetros-mensuales)
6. [Arquitectura de pipelines](#6-arquitectura-de-pipelines)
7. [Sub-proceso: Fletes](#7-sub-proceso-fletes)
8. [Sub-proceso: Cancillería](#8-sub-proceso-cancillería)
9. [Sub-proceso: Consolidación RA](#9-sub-proceso-consolidación-ra)
10. [Sub-proceso: Unión RA (Acumulación Histórica)](#10-sub-proceso-unión-ra-acumulación-histórica)
11. [Utilidades compartidas](#11-utilidades-compartidas)
12. [Patrón de diseño Strategy (vías)](#12-patrón-de-diseño-strategy-vías)
13. [Catálogo de datos](#13-catálogo-de-datos)
14. [Reglas de negocio](#14-reglas-de-negocio)
15. [Resultados verificados](#15-resultados-verificados)
16. [Flujo de uso mensual](#16-flujo-de-uso-mensual)
17. [Pruebas de calidad](#17-pruebas-de-calidad)

---

## 1. Contexto y objetivo

El sistema **EMCES** (Estadísticas de Comercio Exterior de Servicios) procesa mensualmente múltiples fuentes de **Registros Administrativos (RA)** para construir la base estadística de servicios de comercio exterior de Colombia. Este proyecto migra el procesamiento de SAS + R a Python + Kedro.

**Fuentes RA implementadas:**

| Fuente | Origen | Programa de referencia |
|---|---|---|
| Fletes de importación | Archivos BAND por país/vía | `Fletes-EMCES 2025-12.R` |
| Gastos de Cancillería | Bases devengados + gastos | `Cancilleria-EMCES 2026-01.sas` |
| Viajes | *(pendiente — amber en diagrama)* | — |

**Flujo de integración:**

```
[fletes]       → fletes_maestro ─┐
[cancilleria]  → canc_maestro ───┤→ [consolidacion_ra] → base_ra → [union_ra] → histórico acumulado
[viajes]       (pendiente) ──────┘
                                                                        ↓ (futuro)
                                                              [encuesta] + [integracion]
```

---

## 2. Stack tecnológico

| Componente | Versión |
|---|---|
| Python | 3.13.9 |
| Kedro | 1.2.0 |
| kedro-datasets | 9.2.0 |
| pandas | 2.3.3 |
| openpyxl | 3.1.5 |
| pyarrow | 23.0.1 |
| pytest | ~7.2 |

El entorno virtual se encuentra en `.venv/` dentro del proyecto.

---

## 3. Estructura del proyecto

```
emces/
├── conf/base/
│   ├── catalog.yml                      # Definición de ~30 datasets Kedro
│   ├── parameters.yml                   # Parámetros mensuales (fletes, cancillería, union_ra)
│   └── exclusions/
│       └── band_excluir.yml             # ~103 códigos BAND a excluir
├── data/
│   ├── 01_raw/                          # Archivos Excel de entrada + programas de referencia
│   │   ├── FletesDic25.xlsx
│   │   ├── Bases_2026-ENERO.xlsx
│   │   ├── Parametricas_base_EMCES_diseños 4.xlsx
│   │   ├── Fletes-EMCES 2025-12.R       (referencia)
│   │   ├── Cancilleria-EMCES 2026-01.sas (referencia)
│   │   └── UnirBase F2026_01C2026_01.sas (referencia)
│   ├── 02_intermediate/
│   │   ├── fletes_filtrados.parquet     # Fletes agregados por mes/pais/via
│   │   └── canc_base4.parquet           # Cancillería pre-agregación (punto de reentrada)
│   ├── 03_primary/
│   │   ├── fletes_maestro.parquet       # Layout EMCES Fletes (~250 filas/mes)
│   │   ├── canc_maestro.parquet         # Layout EMCES Cancillería (~133 filas/mes)
│   │   ├── base_ra.parquet              # Consolidación mensual fletes + cancillería
│   │   ├── base_ra_acumulada.parquet    # Histórico acumulado (todos los meses)
│   │   └── BaseEMCES-RA_2022-1_F{anof}{mesf}C{anoc}{mesc}.xlsx  # Excel histórico
│   └── 08_reporting/
│       ├── Fletes_EMCES_{ano}_{mes}.xlsx
│       └── Cancilleria_{periodo}_{mes}.xlsx
├── src/emces/
│   ├── utils.py                         # Utilidades y schema RA compartidos
│   ├── pipeline_registry.py             # Registro de pipelines individuales y compuestos
│   ├── pipelines/
│   │   ├── ingestion/                   # Lectura de archivos Fletes
│   │   ├── transformation/              # Preparación M49, filtros y agregación Fletes
│   │   ├── construction/                # Enriquecimiento y registro maestro Fletes
│   │   ├── reporting/                   # Exportación Fletes a Excel
│   │   ├── cancilleria/                 # Pipeline completo Cancillería (14 nodos)
│   │   ├── consolidacion_ra/            # Une fletes_maestro + canc_maestro
│   │   └── union_ra/                    # Acumulación histórica mensual
│   └── strategies/
│       └── via_strategy.py              # Patrón Strategy por modo de transporte
└── tests/
    ├── test_calidad.py                  # 32 pruebas Fletes vs. referencia R
    └── pipelines/cancilleria/
        └── test_nodes.py                # 31 pruebas nodos Cancillería
```

---

## 4. Archivos de entrada

Todos los archivos de entrada deben copiarse a `data/01_raw/` antes de ejecutar.

### 4.1 Archivo de fletes mensual

| Atributo | Valor |
|---|---|
| Patrón de nombre | `Fletes{MesAbr}{anio2d}.xlsx` (ej. `FletesDic25.xlsx`) |
| Hoja | `BAND` |
| Columnas relevantes | `MES`, `VIA`, `BAND`, `TOT_FLET{ano}` |

### 4.2 Archivo de Cancillería mensual

| Atributo | Valor |
|---|---|
| Patrón de nombre | `Bases_{YYYY}-{MESN}.xlsx` (ej. `Bases_2026-ENERO.xlsx`) |
| Hojas | `Devengados_Neto`, `Gastos_Funcionamiento`, `Cancilleria_TRM`, `Cancilleria_P` |

### 4.3 Paramétricas (`Parametricas_base_EMCES_diseños 4.xlsx`)

| Hoja | Contenido |
|---|---|
| `T_P_PAIS-ACUERDOS` | Código ALADI, nombre país, ISO 3166, alpha-3, acuerdos 1/2/3 |
| `T_P_TRM_2022` | TRM mensual desde 2022 (`PERIODO`, `MES`, `TRM_BASE`) |
| `Fletes_M49` | Correlativa ALADI ↔ M49 (`Código_ALADI`, `M49_Code`) |

### 4.4 Histórico RA (para Unión RA)

Copiar el Excel histórico del mes anterior a `data/03_primary/` con el nombre referenciado en `union_ra.archivo_historico` de `parameters.yml`.

---

## 5. Parámetros mensuales

Archivo: `conf/base/parameters.yml`

```yaml
# ── Fletes ────────────────────────────────────────────────────────────────────
ano: "2025"
mes_numero: "12"
archivo_fletes: "FletesDic25.xlsx"
archivo_parametricas: "Parametricas_base_EMCES_diseños 4.xlsx"
ruta_entrada: "data/01_raw"
ruta_salida:  "data/08_reporting"
ruta_primary: "data/03_primary"

# ── Cancillería ───────────────────────────────────────────────────────────────
cancilleria:
  periodo: "2026"
  mes: "01"
  mes_nombre: "ENERO"
  archivo_base: "Bases_2026-ENERO.xlsx"
  hojas:
    devengados: "Devengados_Neto"
    gastos: "Gastos_Funcionamiento"
    trm: "Cancilleria_TRM"
    paises: "Cancilleria_P"
    paises1: "T_P_PAIS-ACUERDOS"

# ── Unión RA (acumulación histórica) ─────────────────────────────────────────
union_ra:
  anof: "26"      # año 2 dígitos último procesamiento Fletes   (%LET ANOF en SAS)
  mesf: "01"      # mes 2 dígitos último procesamiento Fletes   (%LET MESF en SAS)
  anoc: "26"      # año 2 dígitos último procesamiento Cancil.  (%LET ANOC en SAS)
  mesc: "01"      # mes 2 dígitos último procesamiento Cancil.  (%LET MESC en SAS)
  archivo_historico: "BaseEMCES-RA_2022-1_F2512C2601.xlsx"  # histórico mes anterior
  hoja_historico: "RA"
  prefijo_salida: "BaseEMCES-RA_2022-1"
  hoja_salida: "RA"
  fuentes_activas:
    fletes: true        # siempre true en producción
    cancilleria: false  # activar cuando Cancillería esté disponible para el mes
```

**Campos a actualizar cada mes:**

| Parámetro | Ejemplo enero 2026 |
|---|---|
| `ano` | `"2026"` |
| `mes_numero` | `"01"` |
| `archivo_fletes` | `"FletesEne26.xlsx"` |
| `cancilleria.periodo` | `"2026"` |
| `cancilleria.mes` | `"01"` |
| `cancilleria.mes_nombre` | `"ENERO"` |
| `cancilleria.archivo_base` | `"Bases_2026-ENERO.xlsx"` |
| `union_ra.anof/mesf/anoc/mesc` | sufijos del mes procesado |
| `union_ra.archivo_historico` | archivo del mes anterior |

---

## 6. Arquitectura de pipelines

### 6.1 Pipelines registrados

| Pipeline | Nodos | Descripción |
|---|---|---|
| `fletes` | 9 | Fletes mensual (migración de R) |
| `cancilleria` | 14 | Cancillería mensual (migración de SAS) |
| `consolidacion_ra` | 2 | Une fletes_maestro + canc_maestro → base_ra |
| `union_ra` | 3 | Acumulación histórica (migración de UnirBase SAS) |
| `ra` | ~25 | **Compuesto**: fletes + cancilleria + consolidacion_ra |
| `ra_completo` | ~28 | **Compuesto**: ra + union_ra |
| `__default__` | ~28 | Todos los individuales |

### 6.2 Comandos de ejecución

```bash
kedro run                             # flujo completo (igual que __default__)
kedro run --pipeline fletes           # solo fletes
kedro run --pipeline cancilleria      # solo cancillería
kedro run --pipeline ra               # fletes + cancillería + consolidación
kedro run --pipeline ra_completo      # flujo mensual completo con histórico
kedro run --pipeline union_ra         # solo acumulación (requiere parquets previos)
```

### 6.3 Diagrama de flujo de datos

```
data/01_raw/
  FletesDic25.xlsx ──────────────────────────────────────────────────────────┐
  Parametricas_base_EMCES_diseños 4.xlsx ────────────────────────────────────┤
                                                                              ↓
                                                                         [fletes]
                                                                    (ingestion→transformation
                                                                     →construction→reporting)
                                                                              ↓
                                                                  fletes_maestro.parquet ──┐
                                                                  Fletes_EMCES_2025_12.xlsx │
                                                                                            │
  Bases_2026-ENERO.xlsx ──────────────────────────────────────────────────────┐             │
  Parametricas_base_EMCES_diseños 4.xlsx (hoja T_P_PAIS-ACUERDOS) ───────────┤             │
                                                                              ↓             │
                                                                       [cancilleria]        │
                                                                    (14 nodos en 5 etapas)  │
                                                                              ↓             │
                                                                  canc_maestro.parquet ─────┤
                                                                  Cancilleria_2026_01.xlsx  │
                                                                                            ↓
                                                                              [consolidacion_ra]
                                                                                            ↓
                                                                              base_ra.parquet
                                                                                            ↓
  BaseEMCES-RA_..._F2512C2601.xlsx (histórico) ───────────────────────────────┐             │
  (en data/03_primary/)                                                        ↓             │
                                                                          [union_ra]  ←──────┘
                                                                               ↓
                                                         base_ra_acumulada.parquet
                                                         BaseEMCES-RA_..._F2601C2601.xlsx
```

---

## 7. Sub-proceso: Fletes

**Migración de:** `Fletes-EMCES 2025-12.R` (R + tidyverse + openxlsx)

### 7.1 Estructura de nodos

#### ingestion (4 nodos)

| Nodo | Función | Hoja Excel | Inputs adicionales |
|---|---|---|---|
| `leer_fletes` | Lee registros BAND del mes | `BAND` | `params:ano`, `params:mes_numero` (para logging) |
| `leer_m49` | Lee correlativa ALADI↔M49 | `Fletes_M49` | — |
| `leer_pais` | Lee tabla de países y acuerdos | `T_P_PAIS-ACUERDOS` | — |
| `leer_trm` | Lee TRM mensual | `T_P_TRM_2022` | — |

Todos leen con `dtype=str` y normalizan nombres de columna a `snake_case` (equivalente a `janitor::clean_names`).

#### transformation (2 nodos)

| Nodo | Función | Equivalencia R |
|---|---|---|
| `preparar_m49` | Limpia correlativa: extrae `m49_code→m49` y `c_digo_aladi→band` | Sección 7 |
| `unir_fletes_m49` | Join BAND↔M49, aplica exclusiones, filtra `via∈{1,3,4}`, agrupa por `(mes,pais,via)` | Secciones 8-10 |

**Exclusiones BAND:** ~103 códigos en `conf/base/exclusions/band_excluir.yml`.

#### construction (2 nodos)

| Nodo | Función | Equivalencia R |
|---|---|---|
| `enriquecer_con_referencias` | Left join con PAIS (por `pais`) y TRM (por `periodo`, `mes`) | Secciones 11-12 |
| `construir_registro_maestro` | Asigna 65 campos del registro EMCES, calcula montos, filtra ceros, aplica Strategy | Sección 13 |

#### reporting (1 nodo)

| Nodo | Función |
|---|---|
| `exportar_excel` | Renombra columnas a MAYÚSCULA, escribe Excel con openpyxl |

### 7.2 Cálculos monetarios (Fletes)

```python
total_en_dolares     = flet_mes / 1_000        # flet_mes viene en miles USD
total_en_miles_pesos = total_en_dolares / trm_base
```

### 7.3 Campos fijos del layout EMCES (Fletes)

| Campo | Valor |
|---|---|
| `FLUJO_COMERCIAL` | `"IMPORTACIONES FLETES"` |
| `IDNOREMP` | `"777-1"` |
| `AGRUPACION` | `3` → `"Servicios de transporte"` |
| `CSEDE` | `0` |
| `MODO` | `1` |
| `NOVEDAD` | `99` |
| `OCISER` | `1` |

### 7.4 Resultados verificados — Diciembre 2025

| Etapa | Filas |
|---|---|
| Lectura fletes raw | 3.787 |
| Tras exclusión BAND + filtro vías | 256 |
| Eliminadas por `total_en_dolares = 0` | 6 |
| **Registro maestro final** | **250** |

Distribución por modo: Marítimo 104 (41,6%) / Aéreo 82 (32,8%) / Carretera 64 (25,6%)

Tiempo de ejecución del pipeline `fletes`: ~2.8 segundos.

---

## 8. Sub-proceso: Cancillería

**Migración de:** `Cancilleria-EMCES 2026-01.sas`

### 8.1 Estructura de nodos (14 en 5 etapas)

**Etapa 1 — Ingesta (5 nodos):**

| Nodo | Función |
|---|---|
| `canc_leer_devengados` | Hoja `Devengados_Neto` + marca `DESCRIPCION_CABPS='DEVENGADOS'` |
| `canc_leer_gastos` | Hoja `Gastos_Funcionamiento` + marca `DESCRIPCION_CABPS='GASTOS'` |
| `canc_leer_trm` | Hoja `Cancilleria_TRM` (sin normalizar nombres — preserva códigos de moneda) |
| `canc_leer_paises` | Hoja `Cancilleria_P` |
| `canc_leer_paises_acuerdos` | Hoja `T_P_PAIS-ACUERDOS` |

**Etapa 2 — Transformación (5 nodos):**

| Nodo | Equivalencia SAS |
|---|---|
| `canc_construir_base1` | `DATA BASE1; SET DEVENGADOS GASTOS;` + `PERIODO_MES` |
| `canc_filtrar_trm` | `PROC TRANSPOSE` + filtro mes + `TRM_COL = 1/PE` |
| `canc_enriquecer_paises` | `MERGE BASE1↔PAISES BY PAIS` (texto) |
| `canc_enriquecer_trm` | `MERGE BASE2↔TRM BY (PERIODO_MES, MONEDA)` |
| `canc_calcular_monetarios` | `DATA BASE4` + `RENAME codigo_pais→pais` + filtro ceros |

**Etapa 3 — Agregación (1 nodo):**

| Nodo | Equivalencia SAS |
|---|---|
| `canc_agregar_por_pais` | `PROC SQL GROUP BY pais, descripcion_cabps → SUM(total_en_dolares, total_en_miles_pesos)` |

**Etapa 4 — Enriquecimiento (1 nodo):**

| Nodo | Función |
|---|---|
| `canc_enriquecer_acuerdos` | Left join con `T_P_PAIS-ACUERDOS` por código numérico `pais` → ISO 3166, ALPHA-3, acuerdos |

**Etapa 5 — Reporting (2 nodos):**

| Nodo | Función |
|---|---|
| `canc_construir_layout` | Asigna campos fijos EMCES + alinea a ORDEN_FINAL_RA |
| `canc_exportar_excel` | Excel dinámico `Cancilleria_{periodo}_{mes}.xlsx` |

### 8.2 Cálculos monetarios (Cancillería)

```python
trm_col              = 1 / PE                           # PE = tasa dólar→moneda extranjera
total_en_dolares     = (total * tasa_de_cambio) / 1000
total_en_miles_pesos = total_en_dolares * trm_col
```

### 8.3 Campos fijos del layout EMCES (Cancillería)

| Campo | Valor |
|---|---|
| `FLUJO_COMERCIAL` | `"IMPORTACIONES GASTOS DEL GOBIERNO"` |
| `IDNOREMP` | `"999-1"` |
| `AGRUPACION` | `9` |
| `CODIGO` | `291` |
| `CPC` | `"91119"` |
| `DEPARTAMENTO` | `11` (Bogotá D.C.) |
| `MODO` | `2` |

### 8.4 Decisiones de diseño clave (Cancillería)

- TRM se lee **sin** normalizar nombres (para preservar códigos de moneda como columnas)
- `codigo_pais` (de "CÓDIGO PAÍS") reemplaza `pais` texto después del join con PAISES
- PAISES1 se une por código numérico, no por nombre
- `canc_base4` persiste a Parquet como punto de reentrada si falla el reporting

### 8.5 Resultados verificados — Enero 2026

| Etapa | Filas |
|---|---|
| raw_devengados | 102 |
| raw_gastos | 56 |
| BASE1 (concat) | 158 |
| BASE4 (tras filtro ceros) | 158 |
| BASE5 (tras GROUP BY) | **133** |
| **canc_maestro final** | **133** |

---

## 9. Sub-proceso: Consolidación RA

**Función:** Une las fuentes RA del mes corriente en una base única.

### 9.1 Nodos (2)

| Nodo | Función |
|---|---|
| `consolidar_ra` | Concat `fletes_maestro + canc_maestro`, alineados a `ORDEN_FINAL_RA` |
| `generar_resumen_ra` | Estadísticas de auditoría: filas, países, totales USD |

### 9.2 Schema canónico: ORDEN_FINAL_RA

65 columnas definidas en `src/emces/utils.py`. Columnas ausentes en una fuente se rellenan con `NaN`/`""`. Garantiza que Fletes y Cancillería (y futuros Viajes) sean concatenables sin error.

---

## 10. Sub-proceso: Unión RA (Acumulación Histórica)

**Migración de:** `UnirBase F2026_01C2026_01.sas`

### 10.1 Nodos (3)

| Nodo | Equivalencia SAS |
|---|---|
| `leer_base_historica` | `PROC IMPORT RA_0 SHEET='RA'` |
| `acumular_fuentes` | `DATA RA_1; SET RA_0 FLETES_1 [CANCILLERIA_1]; PROC SORT BY PERIODO_MES;` |
| `exportar_base_acumulada` | `PROC EXPORT OUTFILE="...F&ANOF.&MESF.C&ANOC.&MESC..xlsx"` |

### 10.2 Control de fuentes activas

El parámetro `fuentes_activas` en `parameters.yml` replica el mecanismo de comentar/descomentar `PROC IMPORT` en el SAS original:

```yaml
fuentes_activas:
  fletes: true         # siempre activo
  cancilleria: false   # activar cuando Cancillería esté disponible para el mes
```

### 10.3 Convención de nombre de salida

```
{prefijo_salida}_F{anof}{mesf}C{anoc}{mesc}.xlsx
Ejemplo: BaseEMCES-RA_2022-1_F2601C2601.xlsx
```

---

## 11. Utilidades compartidas

**Archivo:** `src/emces/utils.py`

| Función / Constante | Descripción |
|---|---|
| `normalizar_col(nombre)` | NFD + snake_case, maneja tildes y ñ |
| `normalizar_nombres(df)` | Aplica `normalizar_col` a todas las columnas |
| `leer_hoja_excel(ruta, hoja)` | `read_excel` con `dtype=str`, valida existencia de archivo y hoja |
| `validar_columnas(df, requeridas, contexto)` | Lanza `ValueError` con lista de faltantes si no están |
| `alinear_a_schema_ra(df, fuente)` | Proyecta al `ORDEN_FINAL_RA` + normaliza tipos para parquet |
| `ORDEN_FINAL_RA` | Lista de 65 columnas — fuente de verdad única del schema RA |
| `_COLS_NUMERICAS_RA` | Set de columnas que se mantienen `float64` (monetarias) |

### Normalización de tipos en `alinear_a_schema_ra`

Al concatenar fuentes de distinto origen (histórico Excel leído con `dtype=str` vs. parquets con tipos inferidos) se producen columnas `object` con tipos mixtos que pyarrow rechaza. La función normaliza antes de retornar:

- **Columnas en `_COLS_NUMERICAS_RA`** → `pd.to_numeric(errors='coerce')` → `float64`
- **Resto de columnas no-object** → `.astype(str)` → string uniforme

```python
_COLS_NUMERICAS_RA = {
    "total_en_dolares", "total_en_miles_de_pesos", "trm_base",
    "vrocefats", "vroce", "construccion",
    "total_vrocefats_dolares", "total_vroce_dolares", "total_construccion_dolares",
}
```

> **Nota:** Columnas identificadoras numéricas (`csede`, `agrupacion`, `codigo`, `pais_cod_iso_3166`, etc.) se convierten a string. Si en el futuro se agrega una columna numérica computada que deba conservarse como `float64`, incluirla en `_COLS_NUMERICAS_RA`.

---

## 12. Patrón de diseño Strategy (vías)

**Archivo:** `src/emces/strategies/via_strategy.py`

El campo `via` del archivo de fletes determina cuatro atributos de clasificación. En R se usaban bloques `case_when`; en Python se implementa el patrón **Strategy**.

| Estrategia | `via` | `codigo` | `cpc` | `descripcion_cabps` |
|---|---|---|---|---|
| `ViaMaritimaStrategy` | 1 | 208 | 65210 | Transporte marítimo de carga |
| `ViaCarreteraStrategy` | 3 | 225 | 65113 | Transporte de carga por carretera |
| `ViaAereaStrategy` | 4 | 212 | 65310 | Transporte aéreo de carga |

Para agregar un nuevo modo: crear una subclase de `ViaStrategy` y registrarla en `VIA_STRATEGIES` sin tocar ningún otro código.

---

## 13. Catálogo de datos

Archivo: `conf/base/catalog.yml`

| Dataset | Tipo | Capa | Pipeline |
|---|---|---|---|
| `band_excluir` | `yaml.YAMLDataset` | conf | fletes |
| `raw_pais`, `raw_trm`, `raw_fletes`, `raw_m49` | `MemoryDataset` | — | fletes |
| `fletes_filtrados` | `ParquetDataset` | `02_intermediate` | fletes |
| `fletes_enriquecidos` | `MemoryDataset` | — | fletes |
| `fletes_maestro` | `ParquetDataset` | `03_primary` | fletes |
| `canc_raw_*` (×5) | `MemoryDataset` | — | cancilleria |
| `canc_base1` a `canc_base3`, `canc_base5`, `canc_base6` | `MemoryDataset` | — | cancilleria |
| `canc_base4` | `ParquetDataset` | `02_intermediate` | cancilleria |
| `canc_maestro` | `ParquetDataset` | `03_primary` | cancilleria |
| `base_ra` | `ParquetDataset` | `03_primary` | consolidacion_ra |
| `ra_resumen` | `MemoryDataset` | — | consolidacion_ra |
| `ra_historico` | `MemoryDataset` | — | union_ra |
| `base_ra_acumulada` | `ParquetDataset` | `03_primary` | union_ra |
| `union_ra_metadata` | `MemoryDataset` | — | union_ra |

---

## 14. Reglas de negocio

### Filtros Fletes

| Regla | Detalle |
|---|---|
| Exclusión BAND | ~103 códigos (zonas francas, regionales, especiales) |
| Filtro vía | Solo `via ∈ {1, 3, 4}` |
| Filtro monetario | Elimina filas donde `total_en_dolares = 0` o `NaN` |

### Filtros Cancillería

| Regla | Equivalencia SAS |
|---|---|
| `total_en_dolares ≠ 0` | `IF TOTAL_EN_DOLARES=0 THEN DELETE` |
| `total_en_miles_pesos ≠ 0` | `IF TOTAL_EN_MILES_DE_PESOS=0 THEN DELETE` |

### Cálculos monetarios

| Pipeline | Fórmula |
|---|---|
| Fletes | `total_en_dolares = flet_mes / 1000` |
| Fletes | `total_en_miles_pesos = total_en_dolares / trm_base` |
| Cancillería | `trm_col = 1 / PE` |
| Cancillería | `total_en_dolares = (total × tasa_de_cambio) / 1000` |
| Cancillería | `total_en_miles_pesos = total_en_dolares × trm_col` |

---

## 15. Resultados verificados

### Fletes — Diciembre 2025

| Indicador | Valor |
|---|---|
| Filas maestro final | **250** |
| Distribución | Marítimo 104 / Aéreo 82 / Carretera 64 |
| `TOTAL_EN_DOLARES` (suma) | 288.937,641330 |
| `TOTAL_EN_MILES_DE_PESOS` (suma) | 1.095.498.958,21 |
| Diferencia vs. script R | `0.00e+00` (dólares) / `3.63e-05` (pesos — punto flotante) |
| Tiempo de ejecución | ~5 segundos |

### Cancillería — Enero 2026

| Indicador | Valor |
|---|---|
| raw_devengados | 102 filas |
| raw_gastos | 56 filas |
| Filas maestro final (`canc_maestro`) | **133** |

### Consolidación RA — 18 abril 2026

| Dataset | Filas |
|---|---|
| `base_ra.parquet` | 383 (250 fletes Dic-2025 + 133 cancillería Ene-2026) |

### Unión RA — 20 abril 2026

| Indicador | Valor |
|---|---|
| Histórico de entrada (`F2512C2601`) | 18.834 filas |
| Fletes agregados (Ene-2026) | 250 filas |
| **Total acumulado** | **19.084 filas** |
| Períodos cubiertos | 2022_01 .. 2026_01 |
| Archivo de salida | `BaseEMCES-RA_2022-1_F2601C2601.xlsx` |
| Tiempo de ejecución | ~76 segundos (dominado por escritura del Excel histórico grande) |

> Cancillería estuvo INACTIVA en este run (`fuentes_activas.cancilleria: false`).

---

## 16. Flujo de uso mensual

### Paso 1 — Preparar archivos de entrada

```
data/01_raw/
├── Fletes{MesAbr}{anio2d}.xlsx          ← fletes del mes
├── Bases_{YYYY}-{MESN}.xlsx             ← cancillería del mes (si disponible)
└── Parametricas_base_EMCES_diseños 4.xlsx  (actualizar si hay cambios)

data/03_primary/
└── BaseEMCES-RA_2022-1_F{ant_anof}{ant_mesf}C{ant_anoc}{ant_mesc}.xlsx  ← histórico anterior
```

### Paso 2 — Actualizar parameters.yml

Editar `conf/base/parameters.yml` con los valores del mes a procesar (ver sección 5).

### Paso 3 — Ejecutar

```bash
# Flujo completo (fletes + cancillería + consolidación + histórico):
kedro run --pipeline ra_completo

# Solo fletes (si Cancillería no está disponible aún):
kedro run --pipeline fletes

# Activar Cancillería en el histórico cuando esté disponible:
#   1. Cambiar union_ra.fuentes_activas.cancilleria: true en parameters.yml
#   2. kedro run --pipeline union_ra
```

### Paso 4 — Verificar salidas

```
data/08_reporting/
├── Fletes_EMCES_{ano}_{mes_numero}.xlsx
└── Cancilleria_{periodo}_{mes}.xlsx

data/03_primary/
├── BaseEMCES-RA_2022-1_F{anof}{mesf}C{anoc}{mesc}.xlsx  (histórico actualizado)
└── base_ra_acumulada.parquet
```

### Referencia de abreviaciones de mes

| `mes_numero` | `MesAbr` |
|---|---|
| `"01"` | `Ene` |
| `"02"` | `Feb` |
| `"03"` | `Mar` |
| `"04"` | `Abr` |
| `"05"` | `May` |
| `"06"` | `Jun` |
| `"07"` | `Jul` |
| `"08"` | `Ago` |
| `"09"` | `Sep` |
| `"10"` | `Oct` |
| `"11"` | `Nov` |
| `"12"` | `Dic` |

---

## 17. Pruebas de calidad

### Fletes — `tests/test_calidad.py` (32 pruebas)

Compara la salida Python contra `Fletes_EMCES_2025_12_salidaR.xlsx` (referencia R).

| Clase | Pruebas | Qué verifica |
|---|---|---|
| `TestEstructura` | 7 | Filas (250), columnas (73), nombres y orden |
| `TestContenidoCategorico` | 5 | Campos de texto idénticos fila a fila |
| `TestContenidoNumerico` | 6 | Monetarios dentro de tolerancia `1e-6` |
| `TestReglasDeNegocio` | 14 | Códigos vía, unicidad (PAIS,MES,CODIGO), coherencia CPC |
| **Total** | **32** | **32/32 pasan** |

### Cancillería — `tests/pipelines/cancilleria/test_nodes.py` (31 pruebas)

| Cobertura | Nodos testeados |
|---|---|
| 31 pruebas unitarias | `_normalizar_col`, `construir_base1`, `filtrar_y_transformar_trm`, `calcular_campos_monetarios`, `agregar_por_pais`, `construir_layout_emces` |
