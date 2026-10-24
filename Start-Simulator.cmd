@echo off
setlocal
cd /d "%~dp0"
set "SIM_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "SIM_PYTHON=.venv\Scripts\python.exe"
"%SIM_PYTHON%" -c "import numpy" >nul 2>&1
if errorlevel 1 (
  echo Python or NumPy is missing. Follow docs\SIMULATION_GUIDE.md first.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8765 in your browser.
echo Keep this window open during the demonstration.
"%SIM_PYTHON%" python\simulator_server.py
if errorlevel 1 pause
