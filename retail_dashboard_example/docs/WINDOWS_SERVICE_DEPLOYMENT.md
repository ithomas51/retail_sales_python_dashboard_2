# Windows Service Deployment Guide
## Retail Dashboard - Streamlit Application

**Version:** 1.0  
**Last Updated:** 2026-01-20

---

## Overview

This guide covers multiple approaches to deploy `retail_dashboard.py` as a Windows service for production use. Running Streamlit as a service ensures the dashboard starts automatically on boot and restarts on failure.

---

## Deployment Options Comparison

| Method | Complexity | Best For | Auto-Restart | Logging |
|--------|------------|----------|--------------|---------|
| **NSSM** | Low | Quick setup, single server | ✅ Yes | ✅ Built-in |
| **pywin32** | Medium | Python-native, custom logic | ✅ Yes | ⚙️ Manual |
| **Task Scheduler** | Low | Simple cases, dev/test | ❌ Limited | ⚙️ Manual |
| **Docker + Docker Desktop** | Medium | Containerized, portable | ✅ Yes | ✅ Built-in |
| **IIS + wfastcgi** | High | Enterprise, existing IIS | ✅ Yes | ✅ Built-in |

---

## Option 1: NSSM (Recommended)

**NSSM (Non-Sucking Service Manager)** is the simplest and most reliable method for running Python/Streamlit apps as Windows services.

### Installation

1. **Download NSSM:**
   - Visit https://nssm.cc/download
   - Extract to `C:\Tools\nssm\` (or add to PATH)

2. **Verify installation:**
   ```powershell
   C:\Tools\nssm\win64\nssm.exe --version
   ```

### Service Setup

#### Step 1: Create a Batch Launcher

Create `start_dashboard.bat` in the project root:

```batch
@echo off
REM Retail Dashboard Windows Service Launcher
REM --------------------------------------------

cd /d "C:\Users\ithom\Desktop\20260120_RetailSalesOrderDashboard_JoshRequest\sales_2020\retail_dashboard_example"

REM Activate virtual environment (if using venv)
REM call .venv\Scripts\activate.bat

REM Start Streamlit with production settings
python -m streamlit run scripts\retail_dashboard.py ^
    --server.port=8501 ^
    --server.address=0.0.0.0 ^
    --server.headless=true ^
    --browser.gatherUsageStats=false ^
    -- -i data\output
```

#### Step 2: Install Service via NSSM GUI

```powershell
# Open NSSM GUI installer
C:\Tools\nssm\win64\nssm.exe install RetailDashboard
```

Configure in the GUI:
- **Path:** `C:\Users\ithom\Desktop\...\start_dashboard.bat`
- **Startup directory:** `C:\Users\ithom\Desktop\...\retail_dashboard_example`
- **Service name:** `RetailDashboard`

#### Step 2 (Alternative): Install via Command Line

```powershell
# Install the service
$nssm = "C:\Tools\nssm\win64\nssm.exe"
$serviceName = "RetailDashboard"
$projectPath = "C:\Users\ithom\Desktop\20260120_RetailSalesOrderDashboard_JoshRequest\sales_2020\retail_dashboard_example"

# Install service pointing to batch file
& $nssm install $serviceName "$projectPath\start_dashboard.bat"

# Set working directory
& $nssm set $serviceName AppDirectory $projectPath

# Configure stdout/stderr logging
& $nssm set $serviceName AppStdout "$projectPath\logs\dashboard_service.log"
& $nssm set $serviceName AppStderr "$projectPath\logs\dashboard_error.log"

# Enable log rotation
& $nssm set $serviceName AppRotateFiles 1
& $nssm set $serviceName AppRotateBytes 10485760  # 10 MB

# Set startup type to automatic
& $nssm set $serviceName Start SERVICE_AUTO_START

# Set service description
& $nssm set $serviceName Description "Retail Sales Dashboard - Streamlit Application"

# Configure restart on failure
& $nssm set $serviceName AppExit Default Restart
& $nssm set $serviceName AppRestartDelay 5000  # 5 second delay
```

### Service Management

```powershell
$nssm = "C:\Tools\nssm\win64\nssm.exe"

# Start service
& $nssm start RetailDashboard

# Stop service
& $nssm stop RetailDashboard

# Restart service
& $nssm restart RetailDashboard

# Check status
& $nssm status RetailDashboard

# Remove service (when no longer needed)
& $nssm remove RetailDashboard confirm
```

### Access Dashboard

Once running, access at: **http://localhost:8501**

For network access: **http://<server-ip>:8501**

---

## Option 2: pywin32 (Python Native)

Use Python's Windows extensions to create a native Windows service.

### Installation

```powershell
pip install pywin32

# Run post-install (elevated prompt required)
python -m pywin32_postinstall -install
```

### Create Service Script

Create `dashboard_service.py`:

```python
"""
Retail Dashboard Windows Service
Runs Streamlit dashboard as a Windows service using pywin32.
"""
import subprocess
import sys
import os
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import logging

# Service configuration
SERVICE_NAME = "RetailDashboard"
SERVICE_DISPLAY_NAME = "Retail Sales Dashboard"
SERVICE_DESCRIPTION = "Interactive Streamlit dashboard for retail sales analysis"

# Paths
PROJECT_DIR = r"C:\Users\ithom\Desktop\20260120_RetailSalesOrderDashboard_JoshRequest\sales_2020\retail_dashboard_example"
SCRIPT_PATH = os.path.join(PROJECT_DIR, "scripts", "retail_dashboard.py")
DATA_DIR = os.path.join(PROJECT_DIR, "data", "output")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "dashboard_service.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class RetailDashboardService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process = None
        socket.setdefaulttimeout(60)
    
    def SvcStop(self):
        """Stop the service"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        logging.info("Service stop requested")
        
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            logging.info("Streamlit process terminated")
    
    def SvcDoRun(self):
        """Run the service"""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        logging.info("Service starting")
        self.main()
    
    def main(self):
        """Main service loop"""
        os.chdir(PROJECT_DIR)
        
        cmd = [
            sys.executable, "-m", "streamlit", "run",
            SCRIPT_PATH,
            "--server.port=8501",
            "--server.address=0.0.0.0",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
            "--",
            "-i", DATA_DIR
        ]
        
        logging.info(f"Starting Streamlit: {' '.join(cmd)}")
        
        self.process = subprocess.Popen(
            cmd,
            cwd=PROJECT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Wait for stop signal
        while True:
            result = win32event.WaitForSingleObject(self.stop_event, 5000)
            if result == win32event.WAIT_OBJECT_0:
                break
            
            # Check if process is still running
            if self.process.poll() is not None:
                logging.error(f"Streamlit process exited with code {self.process.returncode}")
                # Restart the process
                self.process = subprocess.Popen(
                    cmd,
                    cwd=PROJECT_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                logging.info("Streamlit process restarted")


if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(RetailDashboardService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(RetailDashboardService)
```

### Install & Manage Service

```powershell
# Install the service (elevated prompt)
python dashboard_service.py install

# Start the service
python dashboard_service.py start

# Stop the service
python dashboard_service.py stop

# Remove the service
python dashboard_service.py remove

# Debug mode (run in console)
python dashboard_service.py debug
```

---

## Option 3: Windows Task Scheduler

For simpler deployments or development environments.

### Create Scheduled Task (PowerShell)

```powershell
$projectPath = "C:\Users\ithom\Desktop\20260120_RetailSalesOrderDashboard_JoshRequest\sales_2020\retail_dashboard_example"

$action = New-ScheduledTaskAction `
    -Execute "python" `
    -Argument "-m streamlit run scripts\retail_dashboard.py --server.headless=true -- -i data\output" `
    -WorkingDirectory $projectPath

$trigger = New-ScheduledTaskTrigger -AtStartup

$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName "RetailDashboard" `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Retail Sales Dashboard - Streamlit"
```

### Manage Task

```powershell
# Start manually
Start-ScheduledTask -TaskName "RetailDashboard"

# Stop
Stop-ScheduledTask -TaskName "RetailDashboard"

# Remove
Unregister-ScheduledTask -TaskName "RetailDashboard" -Confirm:$false
```

---

## Option 4: Docker (Containerized)

For portable, consistent deployments.

### Dockerfile

Create `Dockerfile` in project root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY scripts/ ./scripts/
COPY data/output/ ./data/output/
COPY .streamlit/ ./.streamlit/

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "scripts/retail_dashboard.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--", "-i", "data/output"]
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  dashboard:
    build: .
    container_name: retail-dashboard
    ports:
      - "8501:8501"
    volumes:
      - ./data/output:/app/data/output:ro
      - ./logs:/app/logs
    restart: always
    environment:
      - TZ=America/New_York
```

### Run with Docker

```powershell
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f dashboard

# Stop
docker-compose down
```

---

## Production Configuration

### Streamlit Config (.streamlit/config.toml)

```toml
[server]
port = 8501
address = "0.0.0.0"
headless = true
enableCORS = false
enableXsrfProtection = true
maxUploadSize = 200

[browser]
gatherUsageStats = false
serverAddress = "localhost"

[theme]
# Use existing theme configuration
```

### Firewall Rules

```powershell
# Allow inbound connections on port 8501
New-NetFirewallRule `
    -DisplayName "Retail Dashboard (Streamlit)" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 8501 `
    -Action Allow
```

### Reverse Proxy (IIS URL Rewrite)

For production, place behind IIS or nginx as reverse proxy:

**IIS web.config:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <system.webServer>
        <rewrite>
            <rules>
                <rule name="ReverseProxyStreamlit" stopProcessing="true">
                    <match url="(.*)" />
                    <action type="Rewrite" url="http://localhost:8501/{R:1}" />
                </rule>
            </rules>
        </rewrite>
    </system.webServer>
</configuration>
```

---

## Monitoring & Logging

### Log Locations

| Method | Log Path |
|--------|----------|
| NSSM | `logs/dashboard_service.log` |
| pywin32 | `logs/dashboard_service.log` |
| Docker | `docker logs retail-dashboard` |

### Health Check Script

Create `check_health.ps1`:

```powershell
# Check if dashboard is responding
$uri = "http://localhost:8501/_stcore/health"
try {
    $response = Invoke-WebRequest -Uri $uri -TimeoutSec 10 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "Dashboard is healthy" -ForegroundColor Green
        exit 0
    }
} catch {
    Write-Host "Dashboard is NOT responding: $_" -ForegroundColor Red
    # Optionally restart the service
    # Restart-Service -Name "RetailDashboard"
    exit 1
}
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Service won't start | Python not in PATH | Use full path to python.exe |
| Port already in use | Another process on 8501 | Change port or kill process |
| Permission denied | Service account lacks access | Run as user with folder access |
| Module not found | Wrong virtual environment | Activate venv in batch file |

### Debug Commands

```powershell
# Check if port is in use
Get-NetTCPConnection -LocalPort 8501

# Check service status
Get-Service -Name "RetailDashboard"

# View Windows Event Log
Get-EventLog -LogName Application -Source "nssm" -Newest 20

# Test Streamlit manually
cd "C:\Users\ithom\Desktop\...\retail_dashboard_example"
streamlit run scripts\retail_dashboard.py -- -i data\output
```

---

## Recommended Approach

For most Windows deployments, **NSSM** is recommended because:

1. ✅ Simple setup (no Python code changes)
2. ✅ Automatic restart on failure
3. ✅ Built-in log rotation
4. ✅ Easy service management
5. ✅ No dependencies beyond NSSM binary

For containerized/cloud deployments, use **Docker**.

---

## Quick Start Checklist

- [ ] Install NSSM to `C:\Tools\nssm\`
- [ ] Create `start_dashboard.bat`
- [ ] Install service: `nssm install RetailDashboard`
- [ ] Configure logging paths
- [ ] Start service: `nssm start RetailDashboard`
- [ ] Configure firewall rule
- [ ] Test: http://localhost:8501
- [ ] Set up monitoring/health checks
