<#
.SYNOPSIS
    Create deployment package for remote machine.
.DESCRIPTION
    Copies all required files for Windows service deployment.
#>

$ProjectPath = "C:\Users\ithom\Desktop\20260120_RetailSalesOrderDashboard_JoshRequest\sales_2020\retail_dashboard_example"
$OutputPath = "C:\Users\ithom\Desktop\RetailDashboard_Deploy"

# Create output folder
if (Test-Path $OutputPath) {
    Remove-Item -Path $OutputPath -Recurse -Force
}
New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null

# Files to copy
$folders = @(
    ".streamlit",
    "scripts",
    "logs"
)

$dataFiles = @(
    "data\output\2020_SalesOrders.csv",
    "data\output\2021_SalesOrders.csv",
    "data\output\2022_SalesOrders.csv",
    "data\output\2023_SalesOrders.csv",
    "data\output\2024_SalesOrders.csv",
    "data\output\2025_SalesOrders.csv",
    "data\output\2026_SalesOrders.csv"
)

$rootFiles = @(
    "start_dashboard.bat",
    "requirements.txt"
)

# Copy folders
foreach ($folder in $folders) {
    $src = Join-Path $ProjectPath $folder
    $dst = Join-Path $OutputPath $folder
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dst -Recurse -Force
        Write-Host "Copied: $folder" -ForegroundColor Green
    }
}

# Create data/output folder and copy CSV files
$dataOutputPath = Join-Path $OutputPath "data\output"
New-Item -ItemType Directory -Path $dataOutputPath -Force | Out-Null

foreach ($file in $dataFiles) {
    $src = Join-Path $ProjectPath $file
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dataOutputPath -Force
        Write-Host "Copied: $file" -ForegroundColor Green
    }
}

# Copy root files
foreach ($file in $rootFiles) {
    $src = Join-Path $ProjectPath $file
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $OutputPath -Force
        Write-Host "Copied: $file" -ForegroundColor Green
    }
}

# Create logs folder if empty
$logsPath = Join-Path $OutputPath "logs"
if (-not (Test-Path $logsPath)) {
    New-Item -ItemType Directory -Path $logsPath -Force | Out-Null
}

# Calculate total size
$totalSize = (Get-ChildItem $OutputPath -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment package created at:" -ForegroundColor Cyan
Write-Host $OutputPath -ForegroundColor Yellow
Write-Host "Total size: $([math]::Round($totalSize, 2)) MB" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "NEXT STEPS - Remote Machine Setup" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. COPY FILES" -ForegroundColor Yellow
Write-Host "   Copy the folder to remote machine:"
Write-Host "   $OutputPath -> C:\RetailDashboard\"
Write-Host ""
Write-Host "2. INSTALL PYTHON (if not installed)" -ForegroundColor Yellow
Write-Host "   - Download: https://www.python.org/downloads/"
Write-Host "   - Check 'Add Python to PATH' during install"
Write-Host "   - Verify: python --version"
Write-Host ""
Write-Host "3. INSTALL DEPENDENCIES" -ForegroundColor Yellow
Write-Host "   cd C:\RetailDashboard"
Write-Host "   pip install -r requirements.txt"
Write-Host ""
Write-Host "4. TEST LOCALLY FIRST" -ForegroundColor Yellow
Write-Host "   cd C:\RetailDashboard"
Write-Host "   streamlit run scripts\retail_dashboard.py -- -i data\output"
Write-Host "   Access: http://localhost:54947"
Write-Host ""
Write-Host "5. INSTALL NSSM (Windows Service Manager)" -ForegroundColor Yellow
Write-Host "   - Download: https://nssm.cc/download"
Write-Host "   - Extract to: C:\Tools\nssm\"
Write-Host ""
Write-Host "6. INSTALL AS WINDOWS SERVICE (Run as Admin)" -ForegroundColor Yellow
Write-Host "   cd C:\RetailDashboard\scripts"
Write-Host "   .\Install-DashboardService.ps1 -Install"
Write-Host "   .\Install-DashboardService.ps1 -Start"
Write-Host ""
Write-Host "7. CONFIGURE FIREWALL (Run as Admin)" -ForegroundColor Yellow
Write-Host "   New-NetFirewallRule -DisplayName 'Retail Dashboard' ``"
Write-Host "       -Direction Inbound -Protocol TCP -LocalPort 54947 -Action Allow"
Write-Host ""
Write-Host "8. ACCESS DASHBOARD" -ForegroundColor Yellow
Write-Host "   Local:   http://localhost:54947"
Write-Host "   Network: http://<server-ip>:54947"
Write-Host ""
Write-Host "SERVICE MANAGEMENT" -ForegroundColor Cyan
Write-Host "==================" -ForegroundColor Cyan
Write-Host "   .\Install-DashboardService.ps1 -Status    # Check status"
Write-Host "   .\Install-DashboardService.ps1 -Stop      # Stop service"
Write-Host "   .\Install-DashboardService.ps1 -Start     # Start service"
Write-Host "   .\Install-DashboardService.ps1 -Uninstall # Remove service"
Write-Host ""
Write-Host "LOGS" -ForegroundColor Cyan
Write-Host "====" -ForegroundColor Cyan
Write-Host "   C:\RetailDashboard\logs\dashboard_stdout.log"
Write-Host "   C:\RetailDashboard\logs\dashboard_stderr.log"
