@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo First create a .venv and install requirements.txt; see README.md.
 pause
 exit /b 1
)
.venv\Scripts\python.exe run.py
pause
