@echo off
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo The project Python environment is missing. See README.md for setup.
    pause
    exit /b 1
)
if not exist "%~dp0v2\graphics_abstraction\native\bresenham.dll" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0v2\build_native.py"
)
"%~dp0.venv\Scripts\python.exe" "%~dp0v2\main.py" %*
if errorlevel 1 (
    echo.
    echo The game could not start. The error is shown above.
    pause
    exit /b 1
)
