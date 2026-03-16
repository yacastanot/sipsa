@echo off
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════╗
echo  ║      SIPSA Pipeline - App Web        ║
echo  ╚══════════════════════════════════════╝
echo.
echo  Acceso local : http://localhost:8000
echo  Acceso en red: http://%COMPUTERNAME%:8000
echo.
echo  Presiona Ctrl+C para detener el servidor.
echo.

uvicorn app:app --host 0.0.0.0 --port 8000
