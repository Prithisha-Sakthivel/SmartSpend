@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 (echo Could not create the virtual environment. Install Python 3.10 or newer. & exit /b 1)
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
if not exist instance mkdir instance
echo Setup complete. Run run.bat to start SmartSpend.
