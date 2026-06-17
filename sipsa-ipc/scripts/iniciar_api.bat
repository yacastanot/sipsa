@echo off
:: ============================================================
:: SIPSA IPC - Iniciar API REST
:: Ejecutar desde la raiz del proyecto sipsa-ipc
:: La API queda disponible en http://localhost:8000
:: ============================================================
setlocal enabledelayedexpansion

set "PROJ=%~dp0.."
set "UVICORN=%PROJ%\.venv\Scripts\uvicorn.exe"
set "PYTHON=%PROJ%\.venv\Scripts\python.exe"

echo.
echo  ======================================
echo   SIPSA IPC - API REST
echo  ======================================
echo.
echo  URL:  http://localhost:8000
echo  Docs: http://localhost:8000/docs
echo.
echo  Presionar Ctrl+C para detener la API
echo  ======================================
echo.

if not exist "%UVICORN%" (
    echo [ERROR] No se encontro uvicorn en .venv
    echo         Ejecutar: pip install -e .
    pause
    exit /b 1
)

:: Cargar variables de entorno desde .env si existe
if exist "%PROJ%\.env" (
    for /f "usebackq tokens=1,2 delims==" %%A in ("%PROJ%\.env") do (
        set "_KEY=%%A"
        if not "!_KEY!"=="" if not "!_KEY:~0,1!"=="#" set "%%A=%%B"
    )
)

cd /d "%PROJ%"
start "SIPSA IPC API" "%UVICORN%" app:app --host 0.0.0.0 --port 8000 --reload
