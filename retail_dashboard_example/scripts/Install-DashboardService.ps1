<#
.SYNOPSIS
    Install Retail Dashboard as a Windows Service using NSSM.

.DESCRIPTION
    This script automates the installation of the Retail Dashboard 
    Streamlit application as a Windows service using NSSM.

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

.EXAMPLE
    .\Install-DashboardService.ps1 -Install
    .\Install-DashboardService.ps1 -Start
    .\Install-DashboardService.ps1 -Status
#>

[CmdletBinding()]
param(
    [string]$NssmPath = "C:\Tools\nssm\win64\nssm.exe",
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Status
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
        Write-Host "Dashboard URL: http://localhost:8501" -ForegroundColor Green
        
        # Test health endpoint
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8501/_stcore/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            Write-Host "Health Check: OK" -ForegroundColor Green
        } catch {
            Write-Host "Health Check: Dashboard may still be starting..." -ForegroundColor Yellow
        }
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
} else {
    Write-Host "Retail Dashboard Service Installer" -ForegroundColor Cyan
    Write-Host "===================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\Install-DashboardService.ps1 -Install    # Install service"
    Write-Host "  .\Install-DashboardService.ps1 -Start      # Start service"
    Write-Host "  .\Install-DashboardService.ps1 -Stop       # Stop service"
    Write-Host "  .\Install-DashboardService.ps1 -Status     # Check status"
    Write-Host "  .\Install-DashboardService.ps1 -Uninstall  # Remove service"
    Write-Host ""
    Write-Host "Prerequisites:" -ForegroundColor Yellow
    Write-Host "  1. Download NSSM from https://nssm.cc/download"
    Write-Host "  2. Extract to C:\Tools\nssm\"
    Write-Host "  3. Run PowerShell as Administrator"
}
