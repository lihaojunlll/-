param(
    [string]$Port = "auto"
)

# Force UTF-8 for mpremote on Windows.
$env:PYTHONUTF8 = "1"

$files = @(
    "Config.py",
    "Algorithm.py",
    "Motor.py",
    "Traction.py",
    "Policy.py",
    "car.py",
    "main.py"
)

foreach ($file in $files) {
    if (-not (Test-Path -LiteralPath $file)) {
        throw "Missing file: $file"
    }
}

if (-not (Get-Command mpremote -ErrorAction SilentlyContinue)) {
    throw "mpremote not found. Run: python -m pip install mpremote"
}

Write-Host "Connecting to device: $Port"
& mpremote connect $Port fs cp @files :
if ($LASTEXITCODE -ne 0) {
    throw "File upload failed."
}

& mpremote connect $Port reset
if ($LASTEXITCODE -ne 0) {
    throw "Device reset failed."
}

Write-Host "Upload complete. Device reset."
