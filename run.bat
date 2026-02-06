@echo off
cd /d "%~dp0"
echo Installing dependencies...
py -m pip install -r requirements.txt
echo.
echo Starting server on http://localhost:8080
echo.
py app.py
pause
