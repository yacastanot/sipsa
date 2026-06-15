# Flujo de datos — SIPSA IPC

De dónde vienen los datos, qué transformaciones sufren y dónde se almacenan.

---

## Origen

**Un archivo Excel mensual** entregado por SIPSA:

```
data/01_raw/Alimentos priorizados may2026_SIPSA.xlsx
```

Contiene 3 hojas que el pipeline usa:

| Hoja | Qué contiene | Pipeline que la lee |
|------|-------------|---------------------|
| `BASE SIPSA_A` | ~547K filas · 3 períodos embebidos (t, t-1, t-12) · 18 columnas | F1 |
| `Artículos_IPC` | Plantilla de 29 artículos con metadatos DANE | F7 (opcional) |
| `Alimentos IPC Vs SIPSA_A` | Tabla correlativa mes actual: artículo IPC ↔ variedades SIPSA | F0 |

---

## Diagrama de extremo a extremo

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ENTRADA                                                                 │
│  data/01_raw/Alimentos priorizados may2026_SIPSA.xlsx                    │
│  (~547K filas · 3 períodos · 18 cols)                                   │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
              ┌─────────────────────┼──────────────────────┐
              ▼                     ▼                       ▼
       [Hoja BASE SIPSA_A]  [Hoja Alimentos IPC]    [Hoja Artículos_IPC]
              │                     │                       │
              │              ┌──────▼──────────────────┐   │ (plantilla T39)
              │              │  F0 · preparation        │   │
              │              │  Valida 3 períodos        │   │
              │              │  Asigna códigos 1001-N   │   │
              │              │  Mapea variedades→arts    │   │
              │              └──────┬──────────────────┘   │
              │                     │ articulos_ipc_actualizado   │
              │                     │ (MemoryDataset)             │
              ▼                     │                             │
       ┌──────────────────┐         │                             │
       │  F1 · ingestion  │         │                             │
       │  Lee con dtype   │         │                             │
       │  Pandera schema  │         │                             │
       └──────┬───────────┘         │                             │
              │                     │                             │
              ▼                     │                             │
   base_sipsa_bronze.parquet        │                             │
   (02_intermediate · ~547K filas)  │                             │
              │                     │                             │
              ▼                     ▼                             │
       ┌──────────────────────────────────┐                       │
       │  F2 · cleaning                    │                       │
       │  Strip texto · normaliza fechas   │                       │
       │  Parsea Fuente → Ciudad+Central   │                       │
       │  Asigna PerFecha (t/t-1/t-12)     │                       │
       │  Cant Kg → Cant_Ton               │                       │
       │  Ali → Artículo_IPC → RArtículo_IPC │                    │
       └──────────────────┬───────────────┘                       │
                          │                                        │
                          ▼                                        │
              base_sipsa_clean.parquet                             │
              (03_primary · ~547K filas · +9 cols nuevas)          │
                          │                                        │
                          ▼                                        │
       ┌──────────────────────────────────┐                        │
       │  F3 · validation                  │                        │
       │  Filtra RArtículo_IPC ≠ NaN       │                        │
       │  Genera No_mapeados_IPC.xlsx      │                        │
       │  Genera COBERTURA.xlsx            │                        │
       └──────────────────┬───────────────┘                        │
                          │                                        │
                          ▼                                        │
              base_ipc_filtrada.parquet                            │
              (03_primary · ~327K filas · solo canasta IPC)        │
                          │                                        │
                          ▼                                        │
       ┌──────────────────────────────────┐                        │
       │  F4 · aggregation                 │                        │
       │  SUM(Cant_Ton) por artículo        │                        │
       │  × período (td_total: 29 filas)   │                        │
       │  × departamento (td_abast: ~500)  │                        │
       │  × ciudad (td_destino: ~500)       │                        │
       │  × país importación (td_otros)    │                        │
       └──────┬─────────────────┬──────────┘                       │
              │                 │                                   │
              ▼                 ▼                                   │
         td_total           td_abast                               │
         td_destino         td_abast_otros                         │
              │                 │                                   │
              │          ┌──────▼──────────────────┐               │
              │          │  F6 · formatting         │               │
              │          │  PropCase departamentos  │               │
              │          │  Correcciones propcase   │               │
              │          │  Ordena por participación│               │
              │          └──────┬──────────────────┘               │
              │                 │                                   │
              │          td_abast_fmt                               │
              │          td_destino_fmt                             │
              │          td_abast_otros_fmt                         │
              │                 │                                   │
              ▼                 │                                   │
       ┌──────────────────┐     │                                   │
       │  F5 · comparison │     │                                   │
       │  VariacMensual   │     │                                   │
       │  VariacAnual     │     │                                   │
       │  Formato BEST12. │     │                                   │
       └──────┬───────────┘     │                                   │
              │                 │                                   │
              ▼                 ▼                                   ▼
       ┌──────────────────────────────────────────────────────────┐
       │  F7 · reporting                                           │
       │  exportar_sipsa_ipc()           → T38 SIPSA_IPC_*.xlsx   │
       │  exportar_alimentos_priorizados()→ T39 Alimentos_prio_*  │
       │  guardar_historico()            → historico_td_total.parq │
       └──────────────────────────────────────────────────────────┘
```

---

## Transformaciones clave

### Columnas nuevas que se crean en F2

| Columna nueva | Tipo | Fuente | Descripción |
|---------------|------|--------|-------------|
| `Ciudad` | str | `Fuente` (split por `,`) | Primera parte de "Ciudad, Central" con correcciones |
| `Central` | str | `Fuente` (split por `,`) | Segunda/tercera parte de la cadena Fuente |
| `Cant_Ton` | float64 | `Cant Kg` ÷ 1000 | Cantidad en toneladas |
| `Año` | Int64 | `FechaEncuesta.year` | Año del registro |
| `Mes` | Int64 | `FechaEncuesta.month` | Mes numérico |
| `Mes2` | str | `Mes` → diccionario | Nombre del mes en español |
| `PerFecha` | str | `Año`, `Mes2`, params | "Mes actual" / "Mes anterior" / "Año anterior" |
| `Artículo_IPC` | str | `Ali` → mapeo F0 | Nombre artículo IPC (ej. "AGUACATE") |
| `RArtículo_IPC` | Int64 | `Artículo_IPC` → código | Código numérico 1001–N asignado en F0 |

### Registros filtrados en F3

| Etapa | Filas | % del total |
|-------|-------|-------------|
| Bronze (F1) | ~547K | 100% |
| Clean (F2) | ~547K | 100% |
| Filtrada canasta IPC (F3) | ~327K | ~60% |

Los ~220K registros excluidos son variedades SIPSA que no hacen parte de la canasta
IPC del mes (artículos sin mapeo en "Alimentos IPC Vs SIPSA_A").

---

## Almacenamiento por capa

| Capa Kedro | Directorio | Formato | Qué guarda |
|------------|-----------|---------|-----------|
| 01_raw | `data/01_raw/` | `.xlsx` | Excel de entrada mensual |
| 02_intermediate | `data/02_intermediate/` | Parquet Snappy | `base_sipsa_bronze` (snapshot inmutable) |
| 03_primary | `data/03_primary/` | Parquet Snappy | `base_sipsa_clean`, `base_ipc_filtrada` |
| 04_feature | `data/04_feature/` | Parquet Snappy | `td_*`, `historico_td_total` |
| 08_reporting | `data/08_reporting/` | `.xlsx` | T38, T39, COBERTURA, No_mapeados |

Los Parquets no persisten entre ejecuciones del pipeline — cada `kedro run` los
regenera desde cero. El único archivo acumulativo es `historico_td_total.parquet`.

---

## Compatibilidad con macros VBA

El T38 `SIPSA_IPC_YYYYMMDD.xlsx` está diseñado para usarse con `FORMATO_SIPSA_IPC.xlsm`:

- **TD_Abast col 9** (`Descr_pegar`): texto multilinea de zonas abastecedoras.
  El macro hace `VLookup(código, TD_Abast!A:I, 9)` para rellenar col I de Artículos_IPC.
- **TD_Destino col 8** (`Descr_pegar`): texto multilinea de destinos.
  El macro hace `VLookup(código, TD_Destino!A:H, 8)` para rellenar col K de Artículos_IPC.

El T39 `Alimentos_priorizados_*.xlsx` replica exactamente el output del macro
"PEGAR DATOS" de `FORMATO_SIPSA_IPC.xlsm`, permitiendo usarlo directamente
sin necesidad de ejecutar el macro.
