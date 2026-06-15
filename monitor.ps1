param(
    [string]$Port = "COM5",
    [int]$Baud = 115200
)

$env:PYTHONUTF8 = "1"

if (-not (Test-Path -LiteralPath "serial_monitor.py")) {
    throw "serial_monitor.py not found."
}

if (-not (Get-Command mpremote -ErrorAction SilentlyContinue)) {
    throw "mpremote not found. Run: python -m pip install mpremote"
}

$mpremotePath = (Get-Command mpremote).Source
$pythonRoot = Split-Path (Split-Path $mpremotePath -Parent) -Parent
$pythonPath = Join-Path $pythonRoot "python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python executable not found: $pythonPath"
}

& $pythonPath -c "import serial" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "pyserial not found. Run: `"$pythonPath`" -m pip install pyserial"
}

Write-Host "Connecting to ESP32 serial port: $Port"
Write-Host "Use Ctrl+] to exit, or Ctrl+C to interrupt the program."
& $pythonPath "serial_monitor.py" --port $Port --baud $Baud
