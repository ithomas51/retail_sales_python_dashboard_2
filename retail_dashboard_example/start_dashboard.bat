@echo off
REM ============================================
REM Retail Dashboard Windows Service Launcher
REM ============================================
REM This batch file is designed to be called by 
REM NSSM or Windows Task Scheduler to run the
REM Streamlit dashboard as a background service.
REM ============================================

REM Change to project directory
cd /d "%~dp0"

REM Set environment variables
set PYTHONUNBUFFERED=1

REM Activate virtual environment if exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Start Streamlit with production settings
python -m streamlit run scripts\retail_dashboard.py ^
    --server.port=8501 ^
    --server.address=0.0.0.0 ^
    --server.headless=true ^
    --browser.gatherUsageStats=false ^
    --server.enableCORS=false ^
    --server.enableXsrfProtection=true ^
    -- -i data\output
