@echo off
:: ============================================================
:: SIPSA-Abastecimiento - Procesar mes actual
:: Ejecutar desde la raiz del proyecto SIPSA-Abastecimiento
:: ============================================================
setlocal

set "PROJ=%~dp0.."
set "KEDRO=%PROJ%\.venv\Scripts\kedro.exe"

echo.
echo  ======================================
echo   SIPSA-Abastecimiento - Pipeline mensual
echo  ======================================
echo.

if not exist "%KEDRO%" (
    echo [ERROR] No se encontro kedro en .venv
    echo         Ejecutar: python -m venv .venv  y  pip install -e .
    pause
    exit /b 1
)

echo  Ejecutando: kedro run
echo.
cd /d "%PROJ%"
"%KEDRO%" run

if errorlevel 1 (
    echo.
    echo  [ERROR] El pipeline fallo. Revisar los mensajes anteriores.
    pause
    exit /b 1
)

echo.
echo  Pipeline completado exitosamente.
echo  Outputs en: data\08_reporting\
echo.
dir /b "%PROJ%\data\08_reporting\*.xlsx" 2>nul
echo.
pause
