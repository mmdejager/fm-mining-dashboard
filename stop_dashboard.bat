@echo off
REM Stops the Mining Tracker if it is running in the background.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*streamlit run app.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Mining Tracker stopped.
timeout /t 3 >nul
