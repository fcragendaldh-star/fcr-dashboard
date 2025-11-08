# PowerShell script to start Streamlit dashboard
Write-Host "Checking for existing Streamlit processes on port 8501..." -ForegroundColor Yellow

# Find and kill processes using port 8501
$processes = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pid in $processes) {
    Write-Host "Killing process $pid on port 8501..." -ForegroundColor Red
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2

Write-Host "Starting Streamlit dashboard..." -ForegroundColor Green
streamlit run FCR_DASHBOARD.py

