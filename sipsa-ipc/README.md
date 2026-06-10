# SIPSA IPC — Pipeline Python/Kedro

Migración del proceso mensual SIPSA IPC de SAS + VBA a Python + Kedro + FastAPI.

**Stack:** Python 3.13 · Kedro 0.19.15 · pandas 2.3 · FastAPI 0.115 · openpyxl 3.1  
**Producción:** `\\DIMPE-D-065\DIMPE\SIPSA\IPC\`

## Uso rápido

```cmd
# 1. Actualizar conf\base\parameters.yml con el mes actual
# 2. Copiar Excel a data\01_raw\
# 3. Ejecutar:
scripts\procesar_mes.bat

# Iniciar API REST:
scripts\iniciar_api.bat
```

## Documentación

| Documento | Descripción |
|-----------|-------------|
| [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) | Arquitectura técnica: pipelines, nodos, decisiones de diseño |
| [docs/MANUAL_API.md](docs/MANUAL_API.md) | Guía de uso de la API REST (todos los endpoints con ejemplos) |
| [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md) | Instalación y configuración en servidor DIMPE-D-065 |
| [docs/CAPACITACION.md](docs/CAPACITACION.md) | Material de capacitación para el equipo DANE |

## Pruebas

```cmd
.venv\Scripts\pytest.exe tests\ -m "not slow" -q
# 277 passed
```

## Equivalencia con SAS

Verificado contra `SIPSA_A_MODELO_IPC.sas` para Abril 2025:
- TD_Total, TD_Abast, TD_Destino, TD_Abast_Otros: diferencia numérica = 0.0
- VariacMensual y VariacAnual: coincidencia exacta en los 29 artículos
- Tiempo de ejecución: ~5-10 s (vs ~3-5 min en SAS)
