# Configuración — SIPSA IPC

Todas las variables de configuración del proyecto. Hay dos fuentes:

1. **`.env`** — credenciales de la interfaz web (no va a Git).
2. **`conf/base/parameters.yml`** — parámetros del mes en curso.
3. **`conf/base/parameters_articulos_ipc.yml`** — tabla maestra correlativa IPC ↔ SIPSA.

---

## 1. Variables de entorno (`.env`)

Crear a partir de `.env.example`:

```cmd
copy .env.example .env
notepad .env
```

| Variable | Tipo | Valor por defecto | Descripción |
|----------|------|------------------|-------------|
| `SIPSA_IPC_USER` | string | `sipsa` | Usuario para acceder a la interfaz web. |
| `SIPSA_IPC_PASS` | string | `cambiar_esta_clave` | Contraseña para acceder a la interfaz web. Cambiar antes de usar en producción. |

El archivo `.env` está en `.gitignore` — nunca subir al repositorio.

### `.env.example` (plantilla sin valores reales)

```env
SIPSA_IPC_USER=sipsa
SIPSA_IPC_PASS=cambiar_esta_clave
```

---

## 2. Parámetros mensuales (`conf/base/parameters.yml`)

Actualizar **al inicio de cada mes** antes de ejecutar el pipeline.

| Parámetro | Tipo | Ejemplo | Descripción |
|-----------|------|---------|-------------|
| `mes_actual_nombre` | string | `"Mayo"` | Nombre en español del mes actual. Debe coincidir exactamente con los datos del Excel (mayúscula inicial). |
| `mes_anterior_nombre` | string | `"Abril"` | Nombre en español del mes anterior. |
| `anio_actual` | int | `2026` | Año del período actual. |
| `anio_anterior` | int | `2025` | Año usado para el comparativo anual (t-12). |
| `fecha_proceso` | string | `"20260615"` | Fecha de proceso en formato `YYYYMMDD`. Se usa en el nombre de los archivos de salida. |
| `archivo_entrada` | string | `"data/01_raw/Alimentos priorizados may2026_SIPSA.xlsx"` | Ruta relativa al Excel de entrada. Separadores con `/` aunque sea Windows. |
| `ruta_raw` | string | `"data/01_raw"` | Directorio de entrada. No cambiar salvo cambio de estructura. |
| `ruta_reporting` | string | `"data/08_reporting"` | Directorio de salida. No cambiar salvo cambio de estructura. |

### Ejemplo completo

```yaml
mes_actual_nombre:    Mayo
mes_anterior_nombre:  Abril
anio_actual:          2026
anio_anterior:        2025
fecha_proceso:        '20260615'
archivo_entrada:      data/01_raw/Alimentos priorizados may2026_SIPSA.xlsx
ruta_raw:             data/01_raw
ruta_reporting:       data/08_reporting
```

---

## 3. Tabla maestra correlativa (`conf/base/parameters_articulos_ipc.yml`)

Define los 29 artículos IPC de la canasta y sus variedades SIPSA equivalentes.

**Frecuencia de actualización:** Solo cuando DANE modifica la canasta IPC o cuando
se agregan/renombran variedades en el Excel de entrada. No actualizar cada mes.

### Estructura

```yaml
articulos_ipc:
  correlativa:
    AGUACATE:
      - Aguacate Choquette
      - Aguacate común
      - Aguacate Hass
    ACEITE:
      - Aceites
    PAPA:
      - Papa criolla amarilla
      - Papa pastusa
      - Papa R-12
      # ...
```

Cada clave es el nombre del artículo IPC en MAYÚSCULAS. Los valores son las variedades
del campo `Ali` del Excel que corresponden a ese artículo.

### Cómo usar

Los códigos numéricos (`RArtículo_IPC = 1001, 1002, ...`) **no se guardan aquí** —
se recalculan automáticamente en F0 cada mes en orden alfabético de los artículos
presentes en la hoja "Alimentos IPC Vs SIPSA_A" del Excel.

Si una variedad SIPSA no aparece en este archivo, el pipeline la clasifica como
"no mapeada" y la incluye en `No_mapeados_IPC.xlsx` para revisión manual.

---

## 4. Catálogo de datos (`conf/base/catalog.yml`)

Define los datasets intermedios de Kedro. No requiere edición en operación normal.

Los parámetros de ruta se pasan directamente desde `parameters.yml`; los archivos Excel
de salida se construyen dentro de los nodos (no a través del catálogo) porque Kedro 0.19
no interpola `${params:...}` en rutas de datasets con OmegaConf.
