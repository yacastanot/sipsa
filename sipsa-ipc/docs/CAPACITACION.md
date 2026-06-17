# Material de Capacitación — SIPSA-Abastecimiento Python/Kedro

**Dirigido a:** Equipo técnico SIPSA — DANE  
**Duración estimada:** 2 horas  
**Prerequisitos:** Conocimiento básico de Excel; no se requiere experiencia en Python

---

## Módulo 1 — ¿Por qué migramos de SAS a Python? (15 min)

### 1.1 Limitaciones del proceso anterior

| Aspecto | SAS + VBA | Python + Kedro |
|---------|-----------|----------------|
| Licencia | Requiere licencia SAS (~USD 10K/año) | Código abierto, gratuito |
| Reproducibilidad | Manual, depende del operador | Automático, siempre igual |
| Verificación | Visual, comparar Excel | 277 pruebas automáticas |
| Trazabilidad | Difícil de auditar | Git: quién cambió qué y cuándo |
| Velocidad | ~3–5 minutos en SAS | ~5–10 segundos en Python |
| Consulta de datos | Abrir Excel | API REST desde cualquier herramienta |

### 1.2 ¿Qué NO cambió?

- Los **datos de entrada** son los mismos (Excel mensual SIPSA).
- Los **resultados de salida** son idénticos al SAS: verificados bit a bit.
- El **proceso mensual** sigue siendo el mismo: actualizar parámetros, ejecutar, revisar.

### 1.3 Verificación de equivalencia

Se compararon los outputs Python vs SAS para el mes de Abril 2025:
- **TD_Total**: 0 diferencias en toneladas y variaciones porcentuales.
- **TD_Abast, TD_Destino, TD_Abast_Otros**: 0 diferencias en todas las columnas numéricas.
- **VariacMensual y VariacAnual**: coincidencia exacta en los 29 artículos.

---

## Módulo 2 — Operación mensual paso a paso (30 min)

### 2.1 Lo único que cambia cada mes

Al inicio de cada mes se actualizan **dos cosas**:

1. El **archivo Excel de entrada** (Base_SIPSA_IPC_mmmAAAA.xlsx)
2. El archivo **`conf/base/parameters.yml`** con las fechas del período

Todo lo demás (código, mappings, estructura) permanece igual.

### 2.2 Procedimiento paso a paso

**Paso 1 — Copiar el Excel mensual**

Copiar el archivo Excel del mes al servidor:
```
Origen:  \\SIPSA\Datos\Base_SIPSA_IPC_may2025.xlsx
Destino: <ruta_proyecto>\data\01_raw\Base_SIPSA_IPC_may2025.xlsx
```

**Paso 2 — Actualizar parameters.yml**

Abrir con Bloc de notas: `conf\base\parameters.yml`

```yaml
# ANTES (Abril):
mes_actual_nombre:    "Abril"
mes_anterior_nombre:  "Marzo"
anio_actual:          2025
fecha_proceso:        "20250502"
archivo_entrada:      "data/01_raw/Base_SIPSA_IPC_abr2025.xlsx"

# DESPUÉS (Mayo):
mes_actual_nombre:    "Mayo"
mes_anterior_nombre:  "Abril"
anio_actual:          2025
fecha_proceso:        "20250603"
archivo_entrada:      "data/01_raw/Base_SIPSA_IPC_may2025.xlsx"
```

**Paso 3 — Ejecutar el pipeline**

Doble clic en `scripts\procesar_mes.bat`.

Aparece una ventana de comandos. Cuando dice:
```
Pipeline execution completed successfully in X.X sec.
```
...el proceso terminó.

**Paso 4 — Verificar los outputs**

Abrir la carpeta `data\08_reporting\`. Deben aparecer los archivos del mes:
- `SIPSA_IPC_20250603.xlsx` ✓
- `Alimentos_priorizados_may-25_SIPSA_20250603.xlsx` ✓
- `COBERTURA.xlsx` ✓
- `No_mapeados_IPC.xlsx` ✓

**Paso 5 — Copiar a la ruta de red**

Copiar `SIPSA_IPC_*.xlsx` a la carpeta compartida del equipo:
```
<ruta_compartida>\Salida\202505\
```

### 2.3 Ejercicio práctico

> Con el instructor: ejecutar el pipeline con datos del mes de prueba.
> Verificar que `SIPSA_IPC_YYYYMMDD.xlsx` coincide con el de referencia SAS.

---

## Módulo 3 — Consultar datos con la API (30 min)

La API permite consultar los datos procesados sin abrir archivos Excel.
Está disponible en el servidor en `http://localhost:8000`.

### 3.1 Exploración con el navegador

Abrir en Chrome o Edge:
```
http://localhost:8000/docs
```

Aparece la documentación interactiva (Swagger UI). Se puede probar cualquier endpoint
directamente desde el navegador haciendo clic en "Try it out".

Para autenticarse en la interfaz web:
1. Clic en "Authorize" (candado)
2. Ingresar la API Key: `clave-secreta-dane-2026`
3. Clic en "Authorize"

### 3.2 Consultas frecuentes

**¿Qué meses están disponibles?**
```
GET /meses
```
Retorna la lista de meses procesados.

**¿Cuántas toneladas de Papa llegaron en Abril 2025?**
```
GET /estadisticas/1001/Abril2025
```
Ver campo `abast_mes_actual`.

**¿Cuáles son los principales departamentos abastecedores de Tomate?**
```
GET /abastecimiento/Abril2025/1019
```
Ver array `departamentos` ordenado por `participacion_pct`.

**¿Cómo varió el abastecimiento de Abril vs Enero?**
```
GET /comparacion/Abril2025/Enero2025
```
Ver campo `variacion_pct` por artículo.

### 3.3 Consultar desde Excel con Power Query

1. En Excel: `Datos → Obtener datos → De otras fuentes → De la Web`
2. Ingresar URL: `http://localhost:8000/estadisticas/1001/Abril2025`
3. En "Encabezados HTTP opcionales": no se requieren para esta consulta
4. Hacer clic en "Aceptar"
5. Excel muestra los datos en formato tabla

> **Consejo:** Guardar la consulta Power Query para reutilizarla cada mes cambiando
> solo el período en la URL.

### 3.4 Ejercicio práctico

> Con el instructor: consultar las estadísticas de 3 artículos distintos.
> Exportar los resultados a una tabla Excel usando Power Query.

---

## Módulo 4 — Monitoreo y solución de problemas (15 min)

### 4.1 ¿Cómo sé si el pipeline terminó bien?

Al final de la ejecución debe aparecer:
```
INFO     Pipeline execution completed successfully in X.X sec.
```

Si hay un error, aparece en rojo con el mensaje. Los errores más comunes son:

| Mensaje | Causa | Solución |
|---------|-------|----------|
| `FileNotFoundError: data/01_raw/...` | Excel no copiado | Copiar el Excel a `data\01_raw\` |
| `KeyError: 'columna'` | Cambio en estructura del Excel | Contactar al técnico SIPSA |
| `ValidationError` | Datos con tipos incorrectos | Revisar el Excel de entrada |

### 4.2 Verificar cobertura de la canasta

Después de cada ejecución, abrir `data\08_reporting\COBERTURA.xlsx`.

- Si dice **29/29**: todos los artículos IPC están cubiertos. ✓
- Si dice menos de 29: algunos artículos no tienen datos ese mes. Revisar
  `No_mapeados_IPC.xlsx` para identificar las variedades SIPSA sin mapeo.

### 4.3 Revisar el log completo

Si hay un problema, abrir el log detallado:
```cmd
cd <ruta_proyecto>
.venv\Scripts\kedro.exe run 2>&1 | more
```

### 4.4 Ejecutar las pruebas automáticas

Para verificar que el código está funcionando correctamente:
```cmd
cd <ruta_proyecto>
.venv\Scripts\pytest.exe tests\ -m "not slow" -q
# Debe mostrar: 277 passed
```

---

## Módulo 5 — Preguntas frecuentes (15 min)

**¿Puedo ejecutar el pipeline dos veces en el mismo mes?**  
Sí. El pipeline sobreescribe los archivos de salida del mismo período. El histórico
(`historico_td_total.parquet`) solo agrega filas si el mes no existe aún; si ya
existe, las actualiza.

**¿Qué pasa si el Excel de entrada tiene un artículo nuevo?**  
Aparecerá en `No_mapeados_IPC.xlsx`. Para incluirlo en la canasta IPC, se debe
agregar el mapeo en `conf/base/parameters_articulos_ipc.yml` y contactar al equipo
técnico para actualizar el código.

**¿Cómo actualizo el código cuando hay una corrección?**  
```cmd
git pull origin main
```
Luego reiniciar la API si está activa.

**¿Puedo acceder a la API desde mi computador personal?**  
Solo desde el equipo donde está instalado el proyecto. La URL es `http://localhost:8000`.

**¿El proceso funciona si el equipo está apagado?**  
El pipeline (`kedro run`) se puede ejecutar desde cualquier equipo con Python instalado
y el código clonado. La API solo está disponible cuando está iniciada en ese equipo.

**¿Dónde quedan los datos históricos?**  
En `data/04_feature/historico_td_total.parquet`. Este archivo se acumula mes a mes
y es la fuente del endpoint `GET /comparacion/...`.

---

## Resumen de comandos esenciales

```cmd
# Activar entorno Python
.venv\Scripts\activate

# Ejecutar pipeline completo
.venv\Scripts\kedro.exe run

# Iniciar API
.venv\Scripts\uvicorn.exe app:app --host 0.0.0.0 --port 8000

# Ejecutar pruebas
.venv\Scripts\pytest.exe tests\ -m "not slow" -q

# Actualizar código
git pull origin main
```

---

## Contacto técnico

Para dudas sobre el código o problemas con el pipeline:

- **Responsable:** Yeferson Castaño
- **Repositorio:** https://github.com/yacastanot/sipsa
- **Documentación completa:** `docs/` en el repositorio
