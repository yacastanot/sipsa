# Guía de Despliegue — SIPSA IPC en Servidor DANE

**Servidor destino:** `\\DIMPE-D-065\DIMPE\SIPSA\IPC\`  
**Sistema operativo:** Windows 10/11 (DANE)  
**Ruta local en servidor:** `C:\DIMPE\SIPSA\IPC\sipsa-ipc\`

---

## 1. Prerrequisitos en el servidor DIMPE-D-065

### 1.1 Python

1. Descargar **Python 3.13** desde https://python.org/downloads/
2. Instalar marcando **"Add Python to PATH"** y **"Install for all users"**
3. Verificar:
   ```cmd
   python --version
   # Python 3.13.x
   ```

### 1.2 Git

1. Descargar Git para Windows desde https://git-scm.com/download/win
2. Instalar con opciones por defecto
3. Verificar:
   ```cmd
   git --version
   # git version 2.x.x
   ```

---

## 2. Primera instalación

Ejecutar todos los comandos en **CMD como Administrador** en el servidor DIMPE-D-065.

### 2.1 Clonar el repositorio

```cmd
cd C:\DIMPE\SIPSA\IPC
git clone https://github.com/yacastanot/sipsa.git
cd sipsa\sipsa-ipc
```

### 2.2 Crear el entorno virtual

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 2.3 Instalar dependencias

```cmd
pip install -e ".[dev]"
```

Esto instala: `kedro`, `pandas`, `openpyxl`, `fastapi`, `uvicorn`, `slowapi`,
`python-dotenv`, `pytest`, y todas las dependencias del pipeline.

### 2.4 Configurar la API Key

Crear el archivo `.env` en `C:\DIMPE\SIPSA\IPC\sipsa\sipsa-ipc\.env`:

```env
SIPSA_API_KEY=clave-secreta-dane-2026
SIPSA_RATE_LIMIT=60/minute
```

> **Importante:** No compartir este archivo. No subir a Git (ya está en `.gitignore`).

### 2.5 Verificar la instalación

```cmd
.venv\Scripts\python.exe -c "import sipsa_ipc; print('OK')"
.venv\Scripts\kedro.exe info
```

---

## 3. Estructura de carpetas en el servidor

```
C:\DIMPE\SIPSA\IPC\sipsa\sipsa-ipc\
├── data\
│   ├── 01_raw\          ← Copiar aquí el Excel mensual
│   ├── 02_intermediate\
│   ├── 03_primary\
│   ├── 04_feature\
│   └── 08_reporting\    ← Outputs: SIPSA_IPC_*.xlsx, etc.
├── conf\base\
│   └── parameters.yml   ← Actualizar cada mes
├── scripts\
│   ├── iniciar_api.bat  ← Iniciar la API
│   └── procesar_mes.bat ← Ejecutar pipeline mensual
└── .env                 ← Clave de API (NO subir a Git)
```

---

## 4. Flujo mensual de operación

### Paso 1 — Actualizar parámetros

Abrir `conf\base\parameters.yml` con Notepad y actualizar:

```yaml
mes_actual_nombre:    "Mayo"           # Nombre del mes actual
mes_anterior_nombre:  "Abril"          # Mes anterior
anio_actual:          2025
anio_anterior:        2024
fecha_proceso:        "20250603"       # YYYYMMDD del día de proceso
archivo_entrada:      "data/01_raw/Base_SIPSA_IPC_may2025.xlsx"
```

### Paso 2 — Copiar el Excel de entrada

Copiar el archivo mensual a:
```
C:\DIMPE\SIPSA\IPC\sipsa\sipsa-ipc\data\01_raw\Base_SIPSA_IPC_may2025.xlsx
```

### Paso 3 — Ejecutar el pipeline

Doble clic en `scripts\procesar_mes.bat` o desde CMD:

```cmd
cd C:\DIMPE\SIPSA\IPC\sipsa\sipsa-ipc
scripts\procesar_mes.bat
```

Duración típica: **5–10 segundos**.

### Paso 4 — Verificar outputs

Los archivos de salida quedan en `data\08_reporting\`:
- `SIPSA_IPC_YYYYMMDD.xlsx` — Informe principal (4 hojas)
- `Alimentos_priorizados_MMM-AA_SIPSA_YYYYMMDD.xlsx` — Resumen
- `COBERTURA.xlsx` — Cobertura de la canasta IPC
- `No_mapeados_IPC.xlsx` — Variedades SIPSA sin mapeo IPC

### Paso 5 — Copiar a la ruta de red (si aplica)

```cmd
copy data\08_reporting\SIPSA_IPC_*.xlsx \\DIMPE-D-065\DIMPE\SIPSA\IPC\Salida\
```

---

## 5. Iniciar la API REST

La API expone los datos procesados para consulta desde Excel, Power BI u otras
herramientas sin necesidad de abrir los archivos Parquet.

### 5.1 Inicio manual

```cmd
cd C:\DIMPE\SIPSA\IPC\sipsa\sipsa-ipc
scripts\iniciar_api.bat
```

La API queda disponible en `http://DIMPE-D-065:8000`.

### 5.2 Inicio automático con Windows Task Scheduler

Para que la API se inicie automáticamente con Windows:

1. Abrir **Programador de tareas** (`taskschd.msc`)
2. Crear tarea básica:
   - **Nombre:** `SIPSA IPC API`
   - **Desencadenador:** Al iniciar el equipo
   - **Acción:** Iniciar un programa
   - **Programa:** `C:\DIMPE\SIPSA\IPC\sipsa\sipsa-ipc\scripts\iniciar_api.bat`
   - **Inicio en:** `C:\DIMPE\SIPSA\IPC\sipsa\sipsa-ipc`
3. Marcar "Ejecutar tanto si el usuario inició sesión como si no"
4. Marcar "Ejecutar con los privilegios más altos"

### 5.3 Verificar que la API está activa

```cmd
curl http://localhost:8000/health
# {"status":"ok","version":"1.0.0"}
```

O abrir en el navegador: `http://DIMPE-D-065:8000/docs`

---

## 6. Actualizaciones de código

Para actualizar el código a la última versión:

```cmd
cd C:\DIMPE\SIPSA\IPC\sipsa
git pull origin main
cd sipsa-ipc
.venv\Scripts\pip.exe install -e ".[dev]" --quiet
```

Si la API está corriendo, reiniciarla después de la actualización.

---

## 7. Firewall de Windows

Para que otros equipos de la red DANE puedan acceder a la API en el puerto 8000:

```cmd
netsh advfirewall firewall add rule ^
  name="SIPSA IPC API" ^
  dir=in action=allow protocol=TCP localport=8000
```

> Verificar con el área de seguridad informática del DANE si se requiere aprobación
> antes de abrir el puerto.

---

## 8. Resolución de problemas comunes

### Error: `ModuleNotFoundError: No module named 'sipsa_ipc'`

El entorno virtual no está activo o la instalación falló:
```cmd
cd C:\DIMPE\SIPSA\IPC\sipsa\sipsa-ipc
.venv\Scripts\pip.exe install -e . --quiet
```

### Error: `FileNotFoundError: data/01_raw/Base_SIPSA_IPC_*.xlsx`

El archivo de entrada no existe. Verificar que:
1. El Excel está en `data\01_raw\`.
2. `parameters.yml` tiene el nombre exacto del archivo.

### Error: `KeyError` en pipeline

Posible cambio en la estructura del Excel de entrada. Revisar:
1. Que las columnas requeridas existen: `Fuente`, `FechaEncuesta`, `Ali`, `Cant Kg`, `Grupo`.
2. Que el encoding del Excel es compatible.

### La API devuelve datos del mes anterior

La API usa la caché en memoria cargada al inicio. Después de ejecutar el pipeline:
1. Reiniciar la API: cerrar la ventana de CMD y ejecutar `scripts\iniciar_api.bat`.
2. O llamar `POST /procesar/{mes}` que recarga la caché automáticamente.

### Puerto 8000 ya en uso

```cmd
netstat -ano | findstr :8000
# Anotar el PID de la última columna
taskkill /PID <PID> /F
```

---

## 9. Respaldo de datos

Los archivos de salida en `data\08_reporting\` deben respaldarse mensualmente en:
```
\\DIMPE-D-065\DIMPE\SIPSA\IPC\Salida\YYYYMM\
```

El histórico acumulado `data\04_feature\historico_td_total.parquet` debe incluirse
en el respaldo, ya que contiene todos los meses procesados anteriores.
