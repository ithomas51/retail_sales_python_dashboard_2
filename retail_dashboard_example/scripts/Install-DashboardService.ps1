<#
.SYNOPSIS
    Install Retail Dashboard as a Windows Service using NSSM.

.DESCRIPTION
    This script automates the installation of the Retail Dashboard 
    Streamlit application as a Windows service using NSSM.
    Also supports running as a background job without NSSM.

.PARAMETER NssmPath
    Path to nssm.exe. Default: C:\Tools\nssm\win64\nssm.exe

.PARAMETER Install
    Install the service

.PARAMETER Uninstall
    Remove the service

.PARAMETER Start
    Start the service

.PARAMETER Stop
    Stop the service

.PARAMETER Status
    Check service status

.PARAMETER Background
    Run as background job (no NSSM required, survives terminal close)

.PARAMETER StopBackground
    Stop background job

.EXAMPLE
    .\Install-DashboardService.ps1 -Install
    .\Install-DashboardService.ps1 -Start
    .\Install-DashboardService.ps1 -Status
    .\Install-DashboardService.ps1 -Background   # No NSSM needed
#>

[CmdletBinding()]
param(
    [string]$NssmPath = "C:\Tools\nssm\win64\nssm.exe",
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Status,
    [switch]$Background,
    [switch]$StopBackground
)

# Configuration
$ServiceName = "RetailDashboard"
$ServiceDisplayName = "Retail Sales Dashboard"
$ServiceDescription = "Interactive Streamlit dashboard for retail sales analysis"
$ProjectPath = Split-Path -Parent $PSScriptRoot
if (-not $ProjectPath) {
    $ProjectPath = $PSScriptRoot
}
$BatchFile = Join-Path $ProjectPath "start_dashboard.bat"
$LogDir = Join-Path $ProjectPath "logs"

# Ensure log directory exists
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

function Test-Admin {
    $currentUser = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentUser.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-NssmExists {
    if (-not (Test-Path $NssmPath)) {
        Write-Host "ERROR: NSSM not found at $NssmPath" -ForegroundColor Red
        Write-Host ""
        Write-Host "Download NSSM from: https://nssm.cc/download" -ForegroundColor Yellow
        Write-Host "Extract to C:\Tools\nssm\ and try again." -ForegroundColor Yellow
        return $false
    }
    return $true
}

function Install-Service {
    Write-Host "Installing $ServiceName service..." -ForegroundColor Cyan
    
    if (-not (Test-Admin)) {
        Write-Host "ERROR: Administrator privileges required. Run PowerShell as Administrator." -ForegroundColor Red
        return
    }
    
    if (-not (Test-NssmExists)) { return }
    
    if (-not (Test-Path $BatchFile)) {
        Write-Host "ERROR: Batch file not found: $BatchFile" -ForegroundColor Red
        return
    }
    
    # Check if service already exists
    $existing = & $NssmPath status $ServiceName 2>&1
    if ($existing -notmatch "Can't open service") {
        Write-Host "Service already exists. Removing first..." -ForegroundColor Yellow
        & $NssmPath stop $ServiceName 2>&1 | Out-Null
        & $NssmPath remove $ServiceName confirm 2>&1 | Out-Null
        Start-Sleep -Seconds 2
    }
    
    # Install service
    & $NssmPath install $ServiceName $BatchFile
    
    # Configure service
    & $NssmPath set $ServiceName AppDirectory $ProjectPath
    & $NssmPath set $ServiceName DisplayName $ServiceDisplayName
    & $NssmPath set $ServiceName Description $ServiceDescription
    
    # Configure logging
    $StdoutLog = Join-Path $LogDir "dashboard_stdout.log"
    $StderrLog = Join-Path $LogDir "dashboard_stderr.log"
    & $NssmPath set $ServiceName AppStdout $StdoutLog
    & $NssmPath set $ServiceName AppStderr $StderrLog
    
    # Enable log rotation (10 MB)
    & $NssmPath set $ServiceName AppRotateFiles 1
    & $NssmPath set $ServiceName AppRotateBytes 10485760
    
    # Set startup type to automatic
    & $NssmPath set $ServiceName Start SERVICE_AUTO_START
    
    # Configure restart on failure
    & $NssmPath set $ServiceName AppExit Default Restart
    & $NssmPath set $ServiceName AppRestartDelay 5000
    
    Write-Host ""
    Write-Host "Service installed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Start service:  .\Install-DashboardService.ps1 -Start"
    Write-Host "  2. Access dashboard: http://localhost:8501"
    Write-Host ""
    Write-Host "Log files:" -ForegroundColor Cyan
    Write-Host "  stdout: $StdoutLog"
    Write-Host "  stderr: $StderrLog"
}

function Uninstall-Service {
    Write-Host "Removing $ServiceName service..." -ForegroundColor Cyan
    
    if (-not (Test-Admin)) {
        Write-Host "ERROR: Administrator privileges required." -ForegroundColor Red
        return
    }
    
    if (-not (Test-NssmExists)) { return }
    
    & $NssmPath stop $ServiceName 2>&1 | Out-Null
    & $NssmPath remove $ServiceName confirm
    
    Write-Host "Service removed." -ForegroundColor Green
}

function Start-DashboardService {
    Write-Host "Starting $ServiceName..." -ForegroundColor Cyan
    
    if (-not (Test-NssmExists)) { return }
    
    & $NssmPath start $ServiceName
    
    Start-Sleep -Seconds 3
    
    # Check if service is running
    $status = & $NssmPath status $ServiceName
    if ($status -match "SERVICE_RUNNING") {
        Write-Host ""
        Write-Host "Service started successfully!" -ForegroundColor Green
        Write-Host "Dashboard available at: http://localhost:8501" -ForegroundColor Cyan
    } else {
        Write-Host "Service may have failed to start. Status: $status" -ForegroundColor Yellow
        Write-Host "Check logs at: $(Join-Path $LogDir 'dashboard_stderr.log')" -ForegroundColor Yellow
    }
}

function Stop-DashboardService {
    Write-Host "Stopping $ServiceName..." -ForegroundColor Cyan
    
    if (-not (Test-NssmExists)) { return }
    
    & $NssmPath stop $ServiceName
    
    Write-Host "Service stopped." -ForegroundColor Green
}

function Get-ServiceStatus {
    if (-not (Test-NssmExists)) { return }
    
    $status = & $NssmPath status $ServiceName 2>&1
    
    Write-Host ""
    Write-Host "Service: $ServiceName" -ForegroundColor Cyan
    Write-Host "Status:  $status"
    
    if ($status -match "SERVICE_RUNNING") {
        Write-Host ""
        Write-Host "Dashboard URL: http://localhost:54947" -ForegroundColor Green
        
        # Test health endpoint
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:54947/_stcore/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            Write-Host "Health Check: OK" -ForegroundColor Green
        } catch {
            Write-Host "Health Check: Dashboard may still be starting..." -ForegroundColor Yellow
        }
    }
}

# Background job functions (no NSSM required)
$PidFile = Join-Path $LogDir "dashboard.pid"

function Start-BackgroundDashboard {
    Write-Host "Starting dashboard as background job..." -ForegroundColor Cyan
    
    # Check if already running
    if (Test-Path $PidFile) {
        $existingPid = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($existingPid) {
            $proc = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "Dashboard already running (PID: $existingPid)" -ForegroundColor Yellow
                Write-Host "URL: http://localhost:54947" -ForegroundColor Green
                return
            }
        }
    }
    
    # Start process hidden (survives terminal close)
    $StdoutLog = Join-Path $LogDir "dashboard_stdout.log"
    $StderrLog = Join-Path $LogDir "dashboard_stderr.log"
    
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "cmd.exe"
    $psi.Arguments = "/c `"$BatchFile`" > `"$StdoutLog`" 2> `"$StderrLog`""
    $psi.WorkingDirectory = $ProjectPath
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    
    $process = [System.Diagnostics.Process]::Start($psi)
    $process.Id | Out-File -FilePath $PidFile -Force
    
    Write-Host ""
    Write-Host "Dashboard started in background!" -ForegroundColor Green
    Write-Host "PID: $($process.Id)" -ForegroundColor Cyan
    Write-Host "URL: http://localhost:54947" -ForegroundColor Green
    Write-Host ""
    Write-Host "Logs:" -ForegroundColor Cyan
    Write-Host "  stdout: $StdoutLog"
    Write-Host "  stderr: $StderrLog"
    Write-Host ""
    Write-Host "To stop: .\Install-DashboardService.ps1 -StopBackground" -ForegroundColor Yellow
}

function Stop-BackgroundDashboard {
    Write-Host "Stopping background dashboard..." -ForegroundColor Cyan
    
    if (-not (Test-Path $PidFile)) {
        Write-Host "No PID file found. Dashboard may not be running." -ForegroundColor Yellow
        return
    }
    
    $pid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($pid) {
        # Kill the cmd process and its children (streamlit)
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            # Get child processes (streamlit, python)
            Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $pid } | ForEach-Object {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "Dashboard stopped (PID: $pid)" -ForegroundColor Green
        } else {
            Write-Host "Process not found. May have already stopped." -ForegroundColor Yellow
        }
    }
    
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

function Get-BackgroundStatus {
    Write-Host ""
    Write-Host "Background Dashboard Status" -ForegroundColor Cyan
    Write-Host "===========================" -ForegroundColor Cyan
    
    if (Test-Path $PidFile) {
        $pid = Get-Content $PidFile -ErrorAction SilentlyContinue
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Status: RUNNING" -ForegroundColor Green
            Write-Host "PID: $pid"
            Write-Host "URL: http://localhost:54947" -ForegroundColor Green
            
            # Health check
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:54947/_stcore/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
                Write-Host "Health: OK" -ForegroundColor Green
            } catch {
                Write-Host "Health: Starting or unavailable..." -ForegroundColor Yellow
            }
        } else {
            Write-Host "Status: STOPPED (stale PID file)" -ForegroundColor Yellow
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "Status: NOT RUNNING" -ForegroundColor Yellow
    }
}

# Main execution
if ($Install) {
    Install-Service
} elseif ($Uninstall) {
    Uninstall-Service
} elseif ($Start) {
    Start-DashboardService
} elseif ($Stop) {
    Stop-DashboardService
} elseif ($Status) {
    Get-ServiceStatus
    Get-BackgroundStatus
} elseif ($Background) {
    Start-BackgroundDashboard
} elseif ($StopBackground) {
    Stop-BackgroundDashboard
} else {
    Write-Host "Retail Dashboard Service Installer" -ForegroundColor Cyan
    Write-Host "===================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "NSSM Service (recommended for production):" -ForegroundColor Yellow
    Write-Host "  .\Install-DashboardService.ps1 -Install    # Install service"
    Write-Host "  .\Install-DashboardService.ps1 -Start      # Start service"
    Write-Host "  .\Install-DashboardService.ps1 -Stop       # Stop service"
    Write-Host "  .\Install-DashboardService.ps1 -Status     # Check status"
    Write-Host "  .\Install-DashboardService.ps1 -Uninstall  # Remove service"
    Write-Host ""
    Write-Host "Background Job (no NSSM required):" -ForegroundColor Yellow
    Write-Host "  .\Install-DashboardService.ps1 -Background      # Start background"
    Write-Host "  .\Install-DashboardService.ps1 -StopBackground  # Stop background"
    Write-Host ""
    Write-Host "Prerequisites for NSSM:" -ForegroundColor Yellow
    Write-Host "  1. Download NSSM from https://nssm.cc/download"
    Write-Host "  2. Extract to C:\Tools\nssm\"
    Write-Host "  3. Run PowerShell as Administrator"
}
