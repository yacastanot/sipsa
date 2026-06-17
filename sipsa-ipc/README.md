# sipsa-ipc

Pipeline mensual que transforma el snapshot SIPSA de precios y cantidades en las tablas
de abastecimiento que alimentan el cálculo del IPC del DANE.
Migración del programa SAS `SIPSA_A_MODELO_IPC.sas` a Python + Kedro + FastAPI.

## Inicio rápido

```cmd
cp .env.example .env                         # 1. Configurar credenciales de API
# Editar conf\base\parameters.yml            # 2. Mes actual, año, nombre de archivo
# Copiar Excel a data\01_raw\                # 3. Archivo mensual de entrada
scripts\procesar_mes.bat                     # 4. Ejecutar pipeline (~5-10 s)
# Resultados en data\08_reporting\           # 5. SIPSA_IPC_*.xlsx y Alimentos_priorizados_*.xlsx
```

Para iniciar la API REST:

```cmd
scripts\iniciar_api.bat
# Interfaz web disponible en: http://localhost:8000
```

## Requisitos

| Componente | Versión mínima | Notas |
|------------|---------------|-------|
| Python | 3.9 | Probado con 3.13 |
| Kedro | 0.19.0 | `pip install -e ".[dev]"` |
| pandas | 2.0 | |
| openpyxl | 3.1 | Escritura de Excel formateado |
| FastAPI | 0.115 | API REST (opcional) |
| S.O. | Windows 10/11 | Producción en DIMPE-D-065 |

## Documentación

| Archivo | Contenido |
|---------|-----------|
| [docs/01_arquitectura.md](docs/01_arquitectura.md) | Decisiones de diseño, diagrama de pipelines |
| [docs/02_instalacion.md](docs/02_instalacion.md) | Instalación paso a paso en servidor DANE |
| [docs/03_configuracion.md](docs/03_configuracion.md) | Variables `.env` y `parameters.yml` |
| [docs/04_modulos.md](docs/04_modulos.md) | Qué hace cada archivo en `src/` |
| [docs/05_flujo_datos.md](docs/05_flujo_datos.md) | Flujo de datos de extremo a extremo |
| [docs/06_git.md](docs/06_git.md) | Convenciones de ramas, commits y PRs |
| [docs/MANUAL_API.md](docs/MANUAL_API.md) | Endpoints REST con ejemplos |

## Estado del proyecto

**Estable** · 277 pruebas · Equivalencia SAS verificada (diferencia = 0.0)
