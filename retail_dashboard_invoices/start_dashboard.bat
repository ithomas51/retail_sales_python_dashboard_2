@echo off
REM Invoice Dashboard Launcher
REM Starts the Streamlit dashboard for invoice analysis

echo ======================================
echo Invoice Dashboard - Starting...
echo ======================================
echo.

cd /d "%~dp0"

echo Launching dashboard at http://localhost:8501
echo Press Ctrl+C to stop the dashboard
echo.

REM Use parent directory .venv (located in sales_2020)
"%~dp0..\.venv\Scripts\python.exe" -m streamlit run scripts/invoice_dashboard.py -- -i data/brightree/invoices

pause
