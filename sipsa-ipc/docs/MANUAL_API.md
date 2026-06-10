# Manual de Usuario — API REST SIPSA IPC

**Versión:** 1.0.0  
**Base URL (producción):** `http://DIMPE-D-065:8000`  
**Base URL (desarrollo):** `http://localhost:8000`  
**Documentación interactiva:** `{base_url}/docs`

---

## 1. Autenticación

Todos los endpoints (excepto `/docs` y `/openapi.json`) requieren el header:

```
X-API-Key: <clave>
```

La clave se configura en el archivo `.env` del servidor:

```env
SIPSA_API_KEY=clave-secreta-dane-2026
```

Si la clave es incorrecta o falta, la API devuelve:

```json
HTTP 403 Forbidden
{"detail": "API Key inválida o ausente."}
```

---

## 2. Formato de período (`{mes}`)

Todos los endpoints que aceptan un período usan el formato:

```
NombreMesAAAA
```

Ejemplos válidos: `Abril2025`, `Mayo2025`, `Enero2026`  
El nombre del mes debe estar en **español**, con la primera letra en mayúscula.

---

## 3. Formato de artículo (`{articulo}`)

Los endpoints de artículo aceptan **código numérico** o **nombre**:

| Formato | Ejemplo | Notas |
|---------|---------|-------|
| Código IPC | `1001` | Siempre funciona; rango 1001–1029 |
| Nombre | `PAPA` | Insensible a mayúsculas; nombre exacto del artículo |

Ver [Tabla de artículos IPC](#9-tabla-de-artículos-ipc) para la lista completa.

---

## 4. Endpoints

### 4.1 `GET /health` — Estado de la API

Verifica que la API está en línea. **No requiere autenticación.**

```bash
curl http://localhost:8000/health
```

**Respuesta 200:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

### 4.2 `GET /meses` — Períodos disponibles

Lista todos los meses procesados disponibles en el histórico.

```bash
curl -H "X-API-Key: dev-key-sipsa" \
     http://localhost:8000/meses
```

**Respuesta 200:**
```json
{
  "periodos": [
    {"mes": "Abril", "anio": 2025, "periodo": "Abril2025"}
  ],
  "total": 1
}
```

---

### 4.3 `GET /abastecimiento/{mes}/{articulo}` — Procedencia por departamento

Retorna las toneladas abastecidas y participación % por departamento de procedencia
para un artículo IPC en el período indicado.

```bash
# Por código
curl -H "X-API-Key: dev-key-sipsa" \
     http://localhost:8000/abastecimiento/Abril2025/1001

# Por nombre
curl -H "X-API-Key: dev-key-sipsa" \
     http://localhost:8000/abastecimiento/Abril2025/PAPA
```

**Respuesta 200:**
```json
{
  "periodo": "Abril2025",
  "articulo_ipc": "Papa",
  "codigo_ipc": 1001,
  "total_ton": 45821.34,
  "departamentos": [
    {
      "departamento": "Cundinamarca",
      "sum_ton": 18432.10,
      "participacion_pct": 40.22
    },
    {
      "departamento": "Boyaca",
      "sum_ton": 12341.87,
      "participacion_pct": 26.94
    }
  ]
}
```

**Errores posibles:**

| Código | Causa |
|--------|-------|
| 404 | Artículo o período no encontrado |
| 422 | Formato de período inválido |

---

### 4.4 `GET /abastecimiento/destinos/{mes}/{articulo}` — Distribución por ciudad destino

Retorna las toneladas y participación % por ciudad de destino.

```bash
curl -H "X-API-Key: dev-key-sipsa" \
     http://localhost:8000/abastecimiento/destinos/Abril2025/1019
```

**Respuesta 200:**
```json
{
  "periodo": "Abril2025",
  "articulo_ipc": "Tomate chonto",
  "codigo_ipc": 1019,
  "total_ton": 8731.22,
  "ciudades": [
    {
      "ciudad": "Bogota D.C.",
      "sum_ton": 3122.45,
      "participacion_pct": 35.76
    }
  ]
}
```

---

### 4.5 `GET /estadisticas/{articulo}/{mes}` — Variaciones y abastecimiento

Endpoint principal. Retorna para un artículo:
- Toneladas de los 3 períodos (mes actual, mes anterior, año anterior).
- Variación mensual y anual en número y formato colombiano (coma decimal).
- Top 5 departamentos abastecedores.
- Top 5 ciudades destino.
- Importaciones (si aplica).

```bash
curl -H "X-API-Key: dev-key-sipsa" \
     http://localhost:8000/estadisticas/1001/Abril2025

# También por nombre
curl -H "X-API-Key: dev-key-sipsa" \
     http://localhost:8000/estadisticas/PAPA/Abril2025
```

**Respuesta 200:**
```json
{
  "periodo": "Abril2025",
  "articulo_ipc": "Papa",
  "codigo_ipc": 1001,
  "abast_mes_actual": 45821.34,
  "abast_mes_anterior": 44109.87,
  "abast_anio_anterior": 47312.00,
  "variac_mensual_pct": 3.879124,
  "variac_anual_pct": -3.15987491238,
  "variac_mensual_fmt": "3,879124468%",
  "variac_anual_fmt": "-3,159874912%",
  "top_departamentos": [
    {"departamento": "Cundinamarca", "sum_ton": 18432.10, "participacion_pct": 40.22}
  ],
  "top_destinos": [
    {"ciudad": "Bogota D.C.", "sum_ton": 15122.45, "participacion_pct": 33.00}
  ],
  "importaciones": []
}
```

> **Nota sobre formato colombiano:** `variac_mensual_fmt` y `variac_anual_fmt` usan
> coma como separador decimal y replican exactamente el formato SAS BEST12. del
> programa original `SIPSA_A_MODELO_IPC.sas`.

---

### 4.6 `GET /comparacion/{periodo_a}/{periodo_b}` — Comparación entre períodos

Compara el abastecimiento de los 29 artículos entre dos períodos del histórico.
La variación se calcula como `(periodo_a - periodo_b) / periodo_b × 100`.

```bash
curl -H "X-API-Key: dev-key-sipsa" \
     http://localhost:8000/comparacion/Abril2025/Enero2025
```

**Respuesta 200:**
```json
{
  "periodo_a": "Abril2025",
  "periodo_b": "Enero2025",
  "articulos": [
    {
      "articulo_ipc": "Papa",
      "codigo_ipc": 1001,
      "abast_periodo_a": 45821.34,
      "abast_periodo_b": 42100.00,
      "variacion_pct": 8.834523
    }
  ]
}
```

**Errores posibles:**

| Código | Causa |
|--------|-------|
| 404 | Uno o ambos períodos no están en el histórico |
| 422 | Formato de período inválido |

---

### 4.7 `POST /procesar/{mes}` — Ejecutar pipeline

Lanza `kedro run` de forma síncrona para el período indicado. Tras la ejecución
exitosa, la API recarga su caché en memoria con los nuevos datos.

**Límite de rate:** 5 req/min (operación costosa ~5-10 s).

**Prerrequisito:** El archivo Excel debe estar en `data/01_raw/` y
`conf/base/parameters.yml` debe tener los parámetros del mes actualizados.

```bash
curl -X POST \
     -H "X-API-Key: dev-key-sipsa" \
     http://localhost:8000/procesar/Mayo2025
```

**Respuesta 202 (éxito):**
```json
{
  "mes": "Mayo2025",
  "estado": "completado",
  "mensaje": "Pipeline ejecutado correctamente para Mayo 2025.",
  "returncode": 0
}
```

**Respuesta 202 (error en pipeline):**
```json
{
  "mes": "Mayo2025",
  "estado": "error",
  "mensaje": "KeyError: 'archivo no encontrado'...",
  "returncode": 1
}
```

---

## 5. Códigos de error HTTP

| Código | Significado |
|--------|-------------|
| 200 | OK — respuesta exitosa |
| 202 | Accepted — pipeline ejecutado (éxito o error; ver campo `estado`) |
| 403 | Forbidden — API Key ausente o incorrecta |
| 404 | Not Found — artículo o período no encontrado |
| 422 | Unprocessable Entity — formato de parámetro inválido |
| 429 | Too Many Requests — límite de rate excedido |
| 504 | Gateway Timeout — pipeline tardó más de 10 minutos |

---

## 6. Ejemplos con Python (requests)

```python
import requests

BASE = "http://DIMPE-D-065:8000"
HEADERS = {"X-API-Key": "clave-secreta-dane-2026"}

# Períodos disponibles
resp = requests.get(f"{BASE}/meses", headers=HEADERS)
periodos = resp.json()["periodos"]
print(f"Períodos disponibles: {[p['periodo'] for p in periodos]}")

# Estadísticas de Papa en Abril 2025
resp = requests.get(f"{BASE}/estadisticas/1001/Abril2025", headers=HEADERS)
datos = resp.json()
print(f"Papa - Mes actual: {datos['abast_mes_actual']:.1f} ton")
print(f"Variación mensual: {datos['variac_mensual_fmt']}")
print(f"Variación anual:   {datos['variac_anual_fmt']}")

# Comparar dos meses
resp = requests.get(f"{BASE}/comparacion/Abril2025/Enero2025", headers=HEADERS)
for art in resp.json()["articulos"]:
    if art["variacion_pct"] > 10:
        print(f"{art['articulo_ipc']}: +{art['variacion_pct']:.1f}%")
```

---

## 7. Ejemplos con Excel / Power Query

En Excel, usar `Datos → Obtener datos → De la Web`:

```
URL: http://DIMPE-D-065:8000/estadisticas/1001/Abril2025
Header: X-API-Key = clave-secreta-dane-2026
```

O desde Power Query (M):

```powerquery
let
    url = "http://DIMPE-D-065:8000/estadisticas/1001/Abril2025",
    headers = [#"X-API-Key" = "clave-secreta-dane-2026"],
    resp = Json.Document(Web.Contents(url, [Headers=headers])),
    topDeptos = Table.FromList(resp[top_departamentos],
                    Record.FieldValues,
                    {"Departamento","Ton","Part%"})
in
    topDeptos
```

---

## 8. Rate limiting

| Endpoint | Límite |
|----------|--------|
| Todos los GET de datos | 60 req/min |
| `POST /procesar/{mes}` | 5 req/min |

Al exceder el límite:
```json
HTTP 429 Too Many Requests
{"error": "Rate limit exceeded: 60 per 1 minute"}
```

---

## 9. Tabla de artículos IPC

| Código | Artículo |
|--------|---------|
| 1001 | Papa |
| 1002 | Yuca |
| 1003 | Platano hartón |
| 1004 | Tomate de árbol |
| 1005 | Cebolla cabezona blanca |
| 1006 | Cebolla cabezona roja |
| 1007 | Cebolla larga |
| 1008 | Zanahoria |
| 1009 | Habichuela |
| 1010 | Arveja verde |
| 1011 | Frijol verde |
| 1012 | Pepino cohombro |
| 1013 | Repollo |
| 1014 | Lechuga batavia |
| 1015 | Acelga |
| 1016 | Espinaca |
| 1017 | Cilantro |
| 1018 | Ahuyama |
| 1019 | Tomate chonto |
| 1020 | Naranja |
| 1021 | Mango comun |
| 1022 | Banano |
| 1023 | Mora de castilla |
| 1024 | Lulo |
| 1025 | Maracuya |
| 1026 | Brocoli |
| 1027 | Coliflor |
| 1028 | Pimentón |
| 1029 | Aguacate |
