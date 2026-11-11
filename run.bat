@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup.bat first. & exit /b 1)
if not defined SMARTSPEND_DEBUG (
  if exist .env (
    findstr /b /c:"SMARTSPEND_DEBUG=" .env >nul
    if errorlevel 1 set SMARTSPEND_DEBUG=1
  ) else set SMARTSPEND_DEBUG=1
)
.venv\Scripts\python.exe run.py
