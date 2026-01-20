<#
.SYNOPSIS
    Start/Stop Retail Dashboard (background process, survives terminal close)

.PARAMETER Start
    Start dashboard in background

.PARAMETER Stop
    Stop dashboard

.PARAMETER Status
    Check if running

.PARAMETER Foreground
    Run in foreground (for testing)

.EXAMPLE
    .\Start-Dashboard.ps1 -Start
    .\Start-Dashboard.ps1 -Stop
    .\Start-Dashboard.ps1 -Status
#>

param(
    [switch]$Start,
    [switch]$Stop,
    [switch]$Status,
    [switch]$Foreground
)

# Configuration
$ProjectPath = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProjectPath "logs"
$PidFile = Join-Path $LogDir "dashboard.pid"
$DataDir = Join-Path $ProjectPath "data\output"
$ScriptPath = Join-Path $ProjectPath "scripts\retail_dashboard.py"
$Port = 54947

# Ensure log directory exists
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

function Get-DashboardStatus {
    if (Test-Path $PidFile) {
        $storedPid = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($storedPid) {
            $proc = Get-Process -Id $storedPid -ErrorAction SilentlyContinue
            if ($proc) {
                return @{ Running = $true; Pid = $storedPid }
            }
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
    return @{ Running = $false; Pid = $null }
}

function Start-Dashboard {
    $status = Get-DashboardStatus
    if ($status.Running) {
        Write-Host "Dashboard already running (PID: $($status.Pid))" -ForegroundColor Yellow
        Write-Host "URL: http://localhost:$Port" -ForegroundColor Green
        return
    }
    
    Write-Host "Starting dashboard..." -ForegroundColor Cyan
    
    $StdoutLog = Join-Path $LogDir "dashboard_stdout.log"
    $StderrLog = Join-Path $LogDir "dashboard_stderr.log"
    
    # Build command
    $streamlitArgs = @(
        "-m", "streamlit", "run", $ScriptPath,
        "--server.port=$Port",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--", "-i", $DataDir
    )
    
    # Start hidden process
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "python"
    $psi.Arguments = $streamlitArgs -join " "
    $psi.WorkingDirectory = $ProjectPath
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    $process.Start() | Out-Null
    
    # Save PID
    $process.Id | Out-File -FilePath $PidFile -Force
    
    # Start async output readers
    Start-Job -ScriptBlock {
        param($proc, $outLog, $errLog)
        $proc.StandardOutput.ReadToEnd() | Out-File $outLog -Append
    } -ArgumentList $process, $StdoutLog | Out-Null
    
    Start-Job -ScriptBlock {
        param($proc, $errLog)
        $proc.StandardError.ReadToEnd() | Out-File $errLog -Append
    } -ArgumentList $process, $StderrLog | Out-Null
    
    Start-Sleep -Seconds 2
    
    Write-Host ""
    Write-Host "Dashboard started!" -ForegroundColor Green
    Write-Host "PID:  $($process.Id)" -ForegroundColor Cyan
    Write-Host "URL:  http://localhost:$Port" -ForegroundColor Green
    Write-Host "Logs: $LogDir" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To stop: .\Start-Dashboard.ps1 -Stop" -ForegroundColor Yellow
}

function Stop-Dashboard {
    $status = Get-DashboardStatus
    if (-not $status.Running) {
        Write-Host "Dashboard is not running." -ForegroundColor Yellow
        return
    }
    
    Write-Host "Stopping dashboard (PID: $($status.Pid))..." -ForegroundColor Cyan
    
    # Kill process tree
    $parentPid = $status.Pid
    Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $parentPid } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Stop-Process -Id $parentPid -Force -ErrorAction SilentlyContinue
    
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    
    Write-Host "Dashboard stopped." -ForegroundColor Green
}

function Show-Status {
    Write-Host ""
    Write-Host "Retail Dashboard Status" -ForegroundColor Cyan
    Write-Host "=======================" -ForegroundColor Cyan
    
    $status = Get-DashboardStatus
    if ($status.Running) {
        Write-Host "Status: RUNNING" -ForegroundColor Green
        Write-Host "PID:    $($status.Pid)"
        Write-Host "URL:    http://localhost:$Port" -ForegroundColor Green
        
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$Port/_stcore/health" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
            Write-Host "Health: OK" -ForegroundColor Green
        } catch {
            Write-Host "Health: Starting..." -ForegroundColor Yellow
        }
    } else {
        Write-Host "Status: STOPPED" -ForegroundColor Yellow
    }
    Write-Host ""
}

function Start-Foreground {
    Write-Host "Starting dashboard in foreground (Ctrl+C to stop)..." -ForegroundColor Cyan
    Write-Host "URL: http://localhost:$Port" -ForegroundColor Green
    Write-Host ""
    
    Set-Location $ProjectPath
    & python -m streamlit run $ScriptPath `
        --server.port=$Port `
        --server.address=0.0.0.0 `
        --server.headless=true `
        -- -i $DataDir
}

# Main
if ($Start) {
    Start-Dashboard
} elseif ($Stop) {
    Stop-Dashboard
} elseif ($Status) {
    Show-Status
} elseif ($Foreground) {
    Start-Foreground
} else {
    Write-Host "Retail Dashboard" -ForegroundColor Cyan
    Write-Host "================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\Start-Dashboard.ps1 -Start       # Start in background"
    Write-Host "  .\Start-Dashboard.ps1 -Stop        # Stop"
    Write-Host "  .\Start-Dashboard.ps1 -Status      # Check status"
    Write-Host "  .\Start-Dashboard.ps1 -Foreground  # Run in terminal"
    Write-Host ""
    Write-Host "Port: $Port"
    Write-Host "URL:  http://localhost:$Port"
}
