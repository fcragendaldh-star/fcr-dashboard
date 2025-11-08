@echo off
echo Checking for existing Streamlit processes on port 8501...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8501 ^| findstr LISTENING') do (
    echo Killing process %%a on port 8501...
    taskkill /F /PID %%a >nul 2>&1
)

timeout /t 2 /nobreak >nul

echo Starting Streamlit dashboard...
streamlit run FCR_DASHBOARD.py

pause

