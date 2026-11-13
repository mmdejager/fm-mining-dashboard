@echo off
REM Starts the Mining Tracker in your browser. First run sets up the Python environment.
cd /d "%~dp0"
set VENV=%USERPROFILE%\.venvs\mining-tracker
if not exist "%VENV%\Scripts\python.exe" (
    echo Setting up Python environment, this takes a minute...
    python -m venv "%VENV%"
    "%VENV%\Scripts\python.exe" -m pip install --upgrade pip
    "%VENV%\Scripts\python.exe" -m pip install -r requirements.txt
)
"%VENV%\Scripts\python.exe" -m streamlit run app.py
