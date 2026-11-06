@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    set "APP_PYTHON=%~dp0.venv\Scripts\python.exe"
) else (
    if exist ".venv\" (
        echo The .venv folder does not contain a Windows Python interpreter.
        echo Recreate the environment using the README instructions.
        pause
        exit /b 1
    )
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python was not found. Follow the setup instructions in README.md.
        pause
        exit /b 1
    )
    set "APP_PYTHON=python"
)
echo Using Python: "%APP_PYTHON%"
echo Starting Portfolio Optimizer... open http://127.0.0.1:7861 in your browser.
"%APP_PYTHON%" app.py
set "APP_EXIT_CODE=%ERRORLEVEL%"
if not "%APP_EXIT_CODE%"=="0" (
    echo.
    echo The app exited with an error. Check the message above.
    echo Install dependencies into the selected Python environment and check your Gurobi license.
    echo See README.md for setup instructions.
)
pause
exit /b %APP_EXIT_CODE%
