param(
    [string]$Port = "COM8",
    [switch]$NoMonitor
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Get-Command mpremote -ErrorAction SilentlyContinue)) {
    throw "mpremote not found. Run: python -m pip install mpremote"
}

Write-Host "Uploading line tracking project to ESP32 on $Port..."

& mpremote connect $Port mkdir :interfaces
& mpremote connect $Port mkdir :algorithms
& mpremote connect $Port mkdir :decisions
& mpremote connect $Port mkdir :applications

& mpremote connect $Port cp (Join-Path $ProjectDir "main.py") :main.py
& mpremote connect $Port cp (Join-Path $ProjectDir "config.py") :config.py

& mpremote connect $Port cp (Join-Path $ProjectDir "interfaces\__init__.py") :interfaces/__init__.py
& mpremote connect $Port cp (Join-Path $ProjectDir "interfaces\motor_driver.py") :interfaces/motor_driver.py
& mpremote connect $Port cp (Join-Path $ProjectDir "interfaces\gray_sensor.py") :interfaces/gray_sensor.py
& mpremote connect $Port cp (Join-Path $ProjectDir "interfaces\attitude_link.py") :interfaces/attitude_link.py

& mpremote connect $Port cp (Join-Path $ProjectDir "algorithms\__init__.py") :algorithms/__init__.py
& mpremote connect $Port cp (Join-Path $ProjectDir "algorithms\line_position.py") :algorithms/line_position.py
& mpremote connect $Port cp (Join-Path $ProjectDir "algorithms\pid.py") :algorithms/pid.py

& mpremote connect $Port cp (Join-Path $ProjectDir "decisions\__init__.py") :decisions/__init__.py
& mpremote connect $Port cp (Join-Path $ProjectDir "decisions\line_following_policy.py") :decisions/line_following_policy.py

& mpremote connect $Port cp (Join-Path $ProjectDir "applications\__init__.py") :applications/__init__.py
& mpremote connect $Port cp (Join-Path $ProjectDir "applications\line_tracking_app.py") :applications/line_tracking_app.py

Write-Host "Upload complete. Resetting ESP32..."
& mpremote connect $Port reset

if (-not $NoMonitor) {
    Write-Host ""
    Write-Host "Opening serial monitor. Exit with Ctrl+C."
    Write-Host ""
    Start-Sleep -Seconds 1
    & (Join-Path $ProjectDir "monitor.ps1") -Port $Port
}
