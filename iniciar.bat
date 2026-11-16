@echo off
title Mi Caja - Sistema de Venta
cd /d "%~dp0"

echo ============================================
echo        MI CAJA - Sistema de Venta
echo ============================================
echo.

REM --- Cerrar cualquier version vieja que haya quedado abierta ---
echo Cerrando versiones anteriores (si las hay)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*app.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo.

REM --- Primera vez: crear entorno e instalar Flask ---
if not exist ".venv\Scripts\python.exe" (
    echo Instalando por primera vez. Esto tarda un momento...
    py -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: No se pudo crear el entorno. Instala Python desde python.org
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    echo.
    echo Instalacion lista.
    echo.
)

echo Abriendo el sistema en tu navegador...
echo (Para cerrar el sistema: cerra esta ventana)
echo.

".venv\Scripts\python.exe" app.py

pause
