@echo off
echo Starting IT Support Frontend...
cd /d "%~dp0frontend"
set HOST=0.0.0.0
npm start
pause
