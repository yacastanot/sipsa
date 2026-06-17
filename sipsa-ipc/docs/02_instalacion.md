# Instalación — SIPSA IPC

**S.O.:** Windows 10/11

---

## Requisitos del sistema

| Componente | Versión | Instalador |
|------------|---------|-----------|
| Python | 3.9+ (probado con 3.13) | https://python.org/downloads/ |
| Git | 2.x | https://git-scm.com/download/win |

Instalar Python marcando **"Add Python to PATH"** e **"Install for all users"**.

Verificar:

```cmd
python --version   # Python 3.13.x
git --version      # git version 2.x.x
```

---

## Primera instalación

Ejecutar en **CMD como Administrador** en el servidor.

### 1. Clonar el repositorio

```cmd
git clone https://github.com/yacastanot/sipsa.git
cd sipsa\sipsa-ipc
```

### 2. Crear el entorno virtual

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 3. Instalar dependencias

```cmd
pip install -e ".[dev]"
```

Instala: `kedro`, `pandas`, `openpyxl`, `fastapi`, `uvicorn`, `slowapi`,
`python-dotenv`, `pandera`, `structlog`, `pytest` y todas sus dependencias.

### 4. Configurar credenciales

Crear `.env` a partir del ejemplo:

```cmd
copy .env.example .env
notepad .env
```

Editar con las claves reales (ver [03_configuracion.md](03_configuracion.md)).

### 5. Verificar la instalación

```cmd
.venv\Scripts\python.exe -c "import sipsa_ipc; print('OK')"
.venv\Scripts\kedro.exe info
.venv\Scripts\pytest.exe tests\ -m "not slow" -q
# 277 passed
```

---

## Flujo mensual de operación

### Paso 1 — Actualizar parámetros

Abrir `conf\base\parameters.yml` con Notepad y editar:

```yaml
mes_actual_nombre:    "Mayo"
mes_anterior_nombre:  "Abril"
anio_actual:          2026
anio_anterior:        2025
fecha_proceso:        "20260603"         # YYYYMMDD
archivo_entrada:      "data/01_raw/Alimentos priorizados may2026_SIPSA.xlsx"
```

### Paso 2 — Copiar el Excel de entrada

```cmd
copy "\\SERVIDOR\Compartido\Alimentos priorizados may2026_SIPSA.xlsx" data\01_raw\
```

### Paso 3 — Ejecutar el pipeline

```cmd
scripts\procesar_mes.bat
# Duración: ~5-10 segundos
```

O directamente:

```cmd
.venv\Scripts\kedro.exe run
```

### Paso 4 — Verificar outputs

Archivos generados en `data\08_reporting\`:

| Archivo | Descripción |
|---------|-------------|
| `SIPSA_IPC_YYYYMMDD.xlsx` | T38: TD_Total, TD_Abast, TD_Destino, TD_Abast_Otros, TREF_Productos |
| `Alimentos_priorizados_*.xlsx` | T39: hoja Artículos_IPC lista para FORMATO_SIPSA_IPC.xlsm |
| `COBERTURA.xlsx` | 29 artículos IPC con cobertura del mes |
| `No_mapeados_IPC.xlsx` | Variedades SIPSA sin mapeo (para curación manual) |

### Paso 5 — Copiar a la ruta de red

```cmd
copy data\08_reporting\SIPSA_IPC_*.xlsx <ruta_compartida>\Salida\
```

---

## API REST

### Inicio manual

```cmd
scripts\iniciar_api.bat
# API disponible en http://localhost:8000
```

### Inicio automático con Windows Task Scheduler

1. Abrir **Programador de tareas** (`taskschd.msc`)
2. Crear tarea básica:
   - Nombre: `SIPSA IPC API`
   - Desencadenador: Al iniciar el equipo
   - Programa: `<ruta_proyecto>\scripts\iniciar_api.bat`
   - Inicio en: `<ruta_proyecto>`
3. Marcar "Ejecutar tanto si el usuario inició sesión como si no"
4. Marcar "Ejecutar con los privilegios más altos"

### Verificar que la API está activa

```cmd
curl http://localhost:8000/health
# {"status":"ok","version":"1.0.0"}
```

---

## Actualizaciones de código

```cmd
git pull origin main
cd sipsa-ipc
.venv\Scripts\pip.exe install -e ".[dev]" --quiet
```

Reiniciar la API después de actualizar.

---

## Configuración de firewall

Para acceso desde otros equipos de la red DANE:

```cmd
netsh advfirewall firewall add rule ^
  name="SIPSA IPC API" ^
  dir=in action=allow protocol=TCP localport=8000
```

Verificar con el área de seguridad informática antes de abrir el puerto.

---

## Resolución de problemas

| Error | Causa probable | Solución |
|-------|---------------|---------|
| `ModuleNotFoundError: No module named 'sipsa_ipc'` | Entorno virtual no activo o instalación fallida | `.venv\Scripts\pip.exe install -e .` |
| `FileNotFoundError: data/01_raw/...xlsx` | Archivo de entrada no existe | Copiar Excel a `data\01_raw\` y revisar `parameters.yml` |
| `KeyError` en pipeline | Cambio en estructura del Excel | Verificar columnas: `Fuente`, `FechaEncuesta`, `Ali`, `Cant Kg`, `Grupo` |
| API devuelve datos del mes anterior | Caché en memoria no recargada | Reiniciar la API o llamar `POST /procesar/{mes}` |
| Puerto 8000 en uso | Proceso previo activo | `netstat -ano \| findstr :8000` → `taskkill /PID <PID> /F` |

---

## Respaldo de datos

Respaldar mensualmente en `<ruta_compartida>\Salida\YYYYMM\`:

- `data\08_reporting\SIPSA_IPC_*.xlsx`
- `data\08_reporting\Alimentos_priorizados_*.xlsx`
- `data\04_feature\historico_td_total.parquet` (acumulado de todos los meses)
