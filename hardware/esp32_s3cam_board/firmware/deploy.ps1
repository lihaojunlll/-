param(
    [string]$Port = "COM12",
    [switch]$NoMonitor
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Get-Command mpremote -ErrorAction SilentlyContinue)) {
    throw "mpremote not found. Run: pip install mpremote"
}

Write-Host "Uploading S3CAM firmware to ESP32 on $Port..."

mpremote connect $Port mkdir :interfaces
mpremote connect $Port mkdir :algorithms

mpremote connect $Port cp (Join-Path $ScriptDir "main.py") :main.py
mpremote connect $Port cp (Join-Path $ScriptDir "config.py") :config.py

mpremote connect $Port cp (Join-Path $ScriptDir "interfaces\__init__.py") :interfaces/__init__.py
mpremote connect $Port cp (Join-Path $ScriptDir "interfaces\mpu6050.py") :interfaces/mpu6050.py
mpremote connect $Port cp (Join-Path $ScriptDir "interfaces\camera.py") :interfaces/camera.py

mpremote connect $Port cp (Join-Path $ScriptDir "algorithms\__init__.py") :algorithms/__init__.py
mpremote connect $Port cp (Join-Path $ScriptDir "algorithms\attitude.py") :algorithms/attitude.py

Write-Host "Upload complete. Resetting..."
mpremote connect $Port reset

if (-not $NoMonitor) {
    Start-Sleep -Seconds 2
    Write-Host ""
    Write-Host "S3CAM serial monitor. Ctrl+C to exit."
    Write-Host ""
    mpremote connect $Port
}
