@echo off
cd /d "%~dp0"
python -m pip install -r requirements-ml.txt
if errorlevel 1 goto failed
set "PYTHONPATH=%CD%\python"
python -m soundscape_ml.train prepare
if errorlevel 1 goto failed
python -m soundscape_ml.train train
if errorlevel 1 goto failed
echo.
echo Training and held-out testing complete.
echo Run Start-Simulator.cmd, then open /ml in the browser.
pause
exit /b 0
:failed
echo.
echo The operation failed. Read the error above; no successful result is claimed.
pause
exit /b 1
