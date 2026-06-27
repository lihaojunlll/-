param(
    [string]$Address = "ws://car-tracker.local:8266/",
    [string]$Password = "12345678"
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Get-Command mpremote -ErrorAction SilentlyContinue)) {
    throw "mpremote not found. Run: python -m pip install mpremote"
}

Write-Host "Wireless deploy to $Address ..."

$mp = "mpremote connect $Address"

# Update files
& mpremote connect $Address mkdir :interfaces 2>$null
& mpremote connect $Address mkdir :algorithms 2>$null
& mpremote connect $Address mkdir :decisions 2>$null
& mpremote connect $Address mkdir :applications 2>$null

& mpremote connect $Address cp (Join-Path $ProjectDir "main.py") :main.py
& mpremote connect $Address cp (Join-Path $ProjectDir "config.py") :config.py

& mpremote connect $Address cp (Join-Path $ProjectDir "interfaces\__init__.py") :interfaces/__init__.py
& mpremote connect $Address cp (Join-Path $ProjectDir "interfaces\motor_driver.py") :interfaces/motor_driver.py
& mpremote connect $Address cp (Join-Path $ProjectDir "interfaces\gray_sensor.py") :interfaces/gray_sensor.py
& mpremote connect $Address cp (Join-Path $ProjectDir "interfaces\attitude_link.py") :interfaces/attitude_link.py
& mpremote connect $Address cp (Join-Path $ProjectDir "interfaces\ble_debug.py") :interfaces/ble_debug.py
& mpremote connect $Address cp (Join-Path $ProjectDir "interfaces\wifi_setup.py") :interfaces/wifi_setup.py

& mpremote connect $Address cp (Join-Path $ProjectDir "algorithms\__init__.py") :algorithms/__init__.py
& mpremote connect $Address cp (Join-Path $ProjectDir "algorithms\line_position.py") :algorithms/line_position.py
& mpremote connect $Address cp (Join-Path $ProjectDir "algorithms\pid.py") :algorithms/pid.py

& mpremote connect $Address cp (Join-Path $ProjectDir "decisions\__init__.py") :decisions/__init__.py
& mpremote connect $Address cp (Join-Path $ProjectDir "decisions\line_following_policy.py") :decisions/line_following_policy.py

& mpremote connect $Address cp (Join-Path $ProjectDir "applications\__init__.py") :applications/__init__.py
& mpremote connect $Address cp (Join-Path $ProjectDir "applications\line_tracking_app.py") :applications/line_tracking_app.py

Write-Host "Wireless deploy complete. Resetting ESP32..."
& mpremote connect $Address reset
