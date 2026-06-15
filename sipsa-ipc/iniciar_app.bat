@echo off
cd /d "%~dp0"

echo.
echo  ==============================================
echo    SIPSA IPC -- Pipeline Mensual  (App Web)
echo  ==============================================
echo.
echo  Acceso local : http://localhost:8080
echo  Acceso en red: http://%COMPUTERNAME%:8080
echo.
echo  Usuario por defecto : sipsa_ipc
echo  Contrasena          : (ver archivo .env)
echo.
echo  Presiona Ctrl+C para detener el servidor.
echo.

.venv\Scripts\uvicorn.exe app:app --host 0.0.0.0 --port 8080
