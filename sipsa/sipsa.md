# SIPSA Precios — Automatización Semanal en Python / Kedro

## 1. Contexto

El **Sistema de Información de Precios y Abastecimiento del Sector Agropecuario (SIPSA)** del DANE
publica semanalmente un boletín con los precios de venta en los principales mercados mayoristas
de Colombia. Este proyecto migra el proceso original (SAS + macro VBA en Excel) a un pipeline
reproducible en Python, estructurado con el framework **Kedro 0.19**.

### Archivo original reemplazado

| Componente original | Equivalente Python |
|---|---|
| `SIPSA_PRECIO_SEMANAL.sas` | 4 pipelines Kedro en `src/sipsa/pipelines/` |
| `Macro_Excel_Formato_Inf_Semanal_SIPSA_P.txt` | Nodo `generar_excel` con openpyxl |

---

## 2. Requisitos

```
Python 3.13.9
kedro 0.19.15
pandas 2.3.3
openpyxl 3.1.5
python-dotenv >= 1.0
kedro-datasets 7.0.0   # incluye pandas.ExcelDataset, pandas.ParquetDataset, yaml.YAMLDataset
```

Instalación (una sola vez):

```bash
cd c:/Users/Jeferson/Kedro/sipsa
pip install -e .
```

---

## 3. Estructura del proyecto

```
sipsa/
│
├── .env                         # ← Parámetros semanales (NO subir al repositorio)
├── .env.example                 # Plantilla de variables de entorno
├── .gitignore
│
├── conf/base/
│   ├── catalog.yml              # Registro de datasets (entrada, intermedios, mappings)
│   ├── parameters.yml           # Lee SIPSA_FECHA y SIPSA_ARCHIVO desde .env
│   └── mappings/
│       ├── productos.yml        # ~250 productos → código numérico (Rproducto)
│       ├── fuentes.yml          # ~70 mercados → código numérico (RFuente)
│       ├── grupos.yml           # 8 grupos de alimentos → código (RGrupo)
│       └── cuadros.yml          # Orden exacto de productos en cada uno de los 8 cuadros
│
├── data/
│   ├── 01_raw/                  # Excel semanal de entrada (se copia aquí cada semana)
│   ├── 02_intermediate/         # precios_transformados.csv
│   ├── 03_primary/              # boletin_filas.csv
│   └── 08_reporting/            # Boletin_{fecha}_python.xlsx  ← SALIDA FINAL
│
└── src/sipsa/
    ├── settings.py              # Carga .env y registra resolver 'env' para OmegaConf
    ├── pipeline_registry.py
    └── pipelines/
        ├── ingestion/           # Lee y valida el Excel de entrada
        ├── transformation/      # Aplica mappings de producto, fuente y grupo
        ├── aggregation/         # Construye las filas del boletín por cuadro
        └── reporting/           # Genera el Excel formateado (reemplaza la macro VBA)
```

---

## 4. Flujo semanal — paso a paso

### Paso 1 — Copiar el archivo de entrada

Copiar el Excel semanal enviado por los recolectores a la carpeta de entrada del proyecto:

```
data/01_raw/Listado a DD mmm AA.xlsx
```

> El archivo debe tener las columnas: `Grupo`, `Producto`, `Fuente`,
> `Min(1)`, `Max(1)`, `P(1)`, `P(-1)`, `Var(1)`, `Tend`.

### Paso 2 — Actualizar el archivo `.env`

Editar [`.env`](.env) con los valores de la semana:

```dotenv
SIPSA_FECHA=06MAR2026
SIPSA_ARCHIVO=Listado a 06 mar 26.xlsx
```

> **No editar** `conf/base/parameters.yml` — ese archivo lee las variables del `.env` automáticamente.

### Paso 3 — Ejecutar el pipeline

Desde la raíz del proyecto:

```bash
kedro run
```

El pipeline tarda aprox. **6 segundos** y genera el archivo:

```
data/08_reporting/Boletin_{fecha}_python.xlsx
```

### Paso 4 — Revisar advertencias (opcional)

El pipeline imprime en consola `WARNING` para:

- **Productos sin código**: aparecen en el Excel pero no están en el catálogo oficial
  (`conf/base/mappings/productos.yml`). Se excluyen del boletín.
- **Fuentes sin código**: mercados que reportaron datos pero no están en
  `conf/base/mappings/fuentes.yml`. Se incluyen al final de cada producto (sin orden específico).

---

## 5. Descripción de cada pipeline

### 5.1 `ingestion` — Lectura y validación

**Nodo:** `leer_entrada`
**Entradas:** `params:ruta_entrada`, `params:archivo_entrada`
**Salida:** `precios_entrada` (MemoryDataset)

Lee el Excel con `pandas.read_excel`, valida que existan las columnas esperadas,
elimina filas vacías y normaliza tipos (precios → float, tendencia → string).

---

### 5.2 `transformation` — Codificación

**Nodo:** `aplicar_mappings`
**Entradas:** `precios_entrada`, `mapping_productos`, `mapping_fuentes`, `mapping_grupos`
**Salida:** `precios_transformados` (.csv)

Añade tres columnas con los códigos numéricos:

| Columna nueva | Fuente del mapeo | Equivalente SAS |
|---|---|---|
| `Rproducto` | `mappings/productos.yml` | Variable `Rproducto` en DATA Boletin1 |
| `RFuente` | `mappings/fuentes.yml` | Variable `RFuente` |
| `RGrupo` | `mappings/grupos.yml` | Variable `RGrupo` |

Las filas con `Rproducto` nulo se descartan (productos fuera del catálogo).

---

### 5.3 `aggregation` — Armado del boletín

**Nodo:** `armar_cuadros`
**Entradas:** `precios_transformados`, `mapping_productos`, `mapping_cuadros`
**Salida:** `boletin_filas` (.csv)

Construye un DataFrame con que representa el contenido completo del boletín.
Cada fila tiene una columna `_tipo` que indica cómo debe renderizarse:

| `_tipo` | Descripción | Equivalente SAS |
|---|---|---|
| `columnas` | Cabecera de columnas (negrita) | `baset2` en SAS |
| `cuadro` | Título del cuadro, ej. "Cuadro 1. Mercados mayoristas..." | `baseia` / `basef2`... |
| `producto` | Nombre del producto (negrita) | `'Productos y mercados2'n` con Rfuente=1000 |
| `dato` | Precio por mercado | Filas de datos con Rfuente mapeado |
| `separador` | Fila vacía entre productos | Rfuente=2000 |

El ordenamiento de mercados dentro de cada producto está implementado con el
**patrón Strategy** (`OrdenMercadosStrategy`). La estrategia por defecto
(`OrdenPorCodigoLuegoAlfabetico`) ordena primero los mercados con código RFuente
ascendente, y al final los sin código de forma alfabética.

El orden de los productos dentro de cada cuadro está definido en `cuadros.yml`.
Los productos sin datos en la semana se omiten automáticamente
(equivale al filtro `if suma_first ne 2` del SAS).

---

### 5.4 `reporting` — Generación del Excel

**Nodo:** `generar_excel`
**Entradas:** `boletin_filas`, `params:fecha`, `params:ruta_salida`
**Salida:** archivo `Boletin_{fecha}_python.xlsx`

Usa `openpyxl` para generar un Excel con formato, **sin necesidad de la macro VBA**.
El renderizado de cada tipo de fila está implementado con el **patrón Strategy**
(`FilaStrategy`): cada clase sabe cómo escribir y estilizar su tipo de fila,
y el registro `_ESTRATEGIAS` despacha al tipo correcto sin condicionales explícitos.

| Tipo de fila | Clase Strategy | Estilo aplicado |
|---|---|---|
| Título de cuadro | `CuadroStrategy` | Fondo azul corporativo, texto blanco negrita |
| Cabecera de columnas | `ColumnasStrategy` | Fondo azul claro, texto negrita |
| Nombre de producto | `ProductoStrategy` | Fondo amarillo claro, texto negrita |
| Datos de mercado | `DatoStrategy` | Texto normal, precios con separador de miles |
| Separador | `SeparadorStrategy` | Fila en blanco (6 pt de alto) |

La primera fila queda fija al hacer scroll (`freeze_panes`).

Para añadir un nuevo tipo de fila: crear una subclase de `FilaStrategy`
e incluirla en `_ESTRATEGIAS` — sin modificar `generar_excel`.

---

## 6. Catálogos de referencia (mappings)

Los archivos YAML en `conf/base/mappings/` son los catálogos maestros.
Se actualizan cuando hay cambios en el universo de productos o mercados.

### 6.1 `productos.yml`

Mapea el nombre exacto del producto (como aparece en el Excel) a un código numérico
de 8 dígitos con la siguiente estructura:

```
[Grupo][Subgrupo][Tipo][Secuencia]
 10    11        001   → Acelga (Cuadro 1, hoja verde)
 60    13        001   → Alas de pollo con costillar (Cuadro 6, pollo)
```

> **Importante:** Los nombres deben coincidir byte a byte con lo que reporta el Excel.
> El archivo usa codificación UTF-8; los acentos del Excel son codepoints Latin-1
> (0xe1=á, 0xe9=é, 0xed=í, 0xf1=ñ, 0xf3=ó, 0xfa=ú).

Para agregar un **producto nuevo**:
1. Añadir la entrada en `productos.yml` con un código apropiado.
2. Añadir el código al cuadro correspondiente en `cuadros.yml` (en la posición deseada).

> **Atención con acentos:** los nombres en el Excel usan codepoints Latin-1 almacenados como Unicode.
> Errores detectados y corregidos durante la migración:
>
> | Nombre incorrecto | Nombre correcto | Error |
> |---|---|---|
> | `Ahuyamón` | `Ahuyamín` | 0xf3 (ó) ≠ 0xed (í) |
> | `Camarón titó` | `Camarón tití` | segunda vocal: 0xf3 ≠ 0xed |
> | `Papa tocañera` | `Papa tocarreña` | nombre completamente diferente |
> | `Rábalo` | `Róbalo` | 0xe1 (á) ≠ 0xf3 (ó) |

#### Productos fuera del catálogo (excluidos del boletín)

Los siguientes productos aparecen en el Excel pero no tienen código asignado
en el catálogo SAS original y se excluyen del boletín:

- `Aguacate Choquette`
- `Panela pulverizada`

Si en algún momento se decide incluirlos, deben agregarse a `productos.yml` y `cuadros.yml`.

### 6.2 `fuentes.yml`

Mapea el nombre del mercado a un código numérico (1001–1134).
Las fuentes sin código se incluyen en el boletín sin ordenación específica.

Para agregar un **mercado nuevo**:
1. Añadir la entrada en `fuentes.yml` con el siguiente código disponible.

#### Mercados sin código (aparecen al final de cada producto)

El siguiente mercado reporta datos semanalmente pero no tiene código en el catálogo
y aparece al final (sin orden específico) en todos los productos que informa:

- `Pereira, La 41-Impala`

### 6.3 `grupos.yml`

Mapea los 8 grupos de alimentos a códigos 1–8. Rara vez cambia.

### 6.4 `cuadros.yml`

Define el orden exacto de productos dentro de cada uno de los 8 cuadros del boletín.
Cada entrada es la lista de `Rproducto` (código) en el orden en que deben aparecer.

---

## 7. Resultados verificados

Comparación entre el output generado por Python y el boletín original del SAS
para la semana del 27 de febrero de 2026:

| Métrica | Python | SAS |
|---|---|---|
| Filas totales en boletín | 5,179 | 5,179 |
| Filas con precios | 4,484 | 4,484 |
| Tiempo de ejecución | ~5–6 seg | ~30 seg |
| Dependencia de SAS | No | Sí |
| Dependencia de macro VBA | No | Sí |

### Diferencias conocidas con el SAS (intencionales)

- **Fuentes sin código**: en el SAS aparecían *antes* del header del producto
  (por el sort de valores nulos en SAS). En Python aparecen *después* de los
  mercados mapeados, antes del separador — comportamiento más legible.
- **Formato del Excel**: estilos aplicados con openpyxl en lugar de la macro VBA.
  El contenido analítico (precios, productos, mercados, tendencias) es idéntico.

---

## 8. Comandos útiles

```bash
# Ejecutar el pipeline completo
kedro run

# Ejecutar solo un pipeline específico
kedro run --pipeline=ingestion
kedro run --pipeline=transformation
kedro run --pipeline=aggregation
kedro run --pipeline=reporting

# Ver el grafo de dependencias (requiere kedro-viz)
kedro viz

# Ver la lista de datasets en el catálogo
kedro catalog list

# Verificar que el proyecto está bien configurado
kedro info
```

---

## 9. Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ValueError: Columnas faltantes` | El Excel no tiene las columnas esperadas | Verificar que el archivo tenga `Grupo`, `Producto`, `Fuente`, `Min(1)`, `Max(1)`, `P(1)`, `P(-1)`, `Tend` |
| `omegaconf.errors.UnsupportedInterpolationType` | Variable de entorno no definida | Verificar que `.env` exista y tenga `SIPSA_FECHA` y `SIPSA_ARCHIVO` |
| `WARNING: X filas excluidas por productos sin código` | Nuevos productos no están en `productos.yml` | Añadir el producto al YAML con su código y cuadro correspondiente |
| `WARNING: X filas con fuentes sin código` | Nuevo mercado no está en `fuentes.yml` | Añadir el mercado al YAML con su código |
| `FileNotFoundError` | El Excel no está en `data/01_raw/` o el nombre en `.env` no coincide | Verificar nombre exacto del archivo (mayúsculas, espacios, extensión) |
| Pipeline no encuentra datos intermedios | `MemoryDataset` no persiste entre sesiones | Ejecutar siempre `kedro run` completo (no desde nodos intermedios) |

---

## 10. API web (app.py)

La API permite ejecutar el pipeline desde un navegador sin usar la terminal.
Está construida con **FastAPI + uvicorn** y protegida con autenticación HTTP Basic.

### 10.1 Configurar credenciales

Añadir al archivo [`.env`](.env) las variables de usuario y contraseña:

```dotenv
SIPSA_USER=sipsa
SIPSA_PASS=cambiar_esta_clave
```

> Si no se definen, la API usa los valores por defecto (`sipsa` / `cambiar_esta_clave`).
> **Cambiarlos antes de exponer el servidor en red.**

### 10.2 Iniciar el servidor

Desde la raíz del proyecto, con el entorno virtual activo:

```bash
# Desarrollo (recarga automática al editar app.py)
uvicorn app:app --reload

# Producción (sin recarga, más estable)
uvicorn app:app --host 0.0.0.0 --port 8000
```

La interfaz queda disponible en: **http://localhost:8000**

### 10.3 Endpoints disponibles

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Interfaz web (formulario para subir y ejecutar) |
| `POST` | `/upload` | Sube el Excel semanal a `data/01_raw/` |
| `POST` | `/run` | Ejecuta `kedro run` con los parámetros indicados (streaming de logs) |
| `GET` | `/status` | Devuelve `{"running": true/false}` |
| `GET` | `/outputs` | Lista los boletines generados en `data/08_reporting/` |
| `GET` | `/download/{filename}` | Descarga un boletín por nombre de archivo |

Todos los endpoints requieren autenticación HTTP Basic.

### 10.4 Flujo de uso desde el navegador

1. Abrir **http://localhost:8000** e ingresar usuario y contraseña.
2. Subir el Excel semanal con el formulario de carga.
3. Completar los campos `fecha` (ej. `06MAR2026`) y `archivo` (ej. `Listado a 06 mar 26.xlsx`).
4. Hacer clic en **Ejecutar** — los logs del pipeline se muestran en tiempo real.
5. Al terminar, descargar el boletín desde la lista de archivos generados.
