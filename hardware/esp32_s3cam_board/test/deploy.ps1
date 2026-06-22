param(
    [string]$Port = "COM13"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Get-Command mpremote -ErrorAction SilentlyContinue)) {
    throw "mpremote not found."
}

$ConfigFile = Join-Path $ScriptDir "car_config.py"
$TestFile = Join-Path $ScriptDir "test_main.py"

$mode = (Select-String -LiteralPath $ConfigFile -Pattern 'TEST_MODE\s*=\s*"([^"]+)"' | Select-Object -First 1).Matches.Groups[1].Value
Write-Host "TEST_MODE: $mode"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

$cfgBytes = [System.IO.File]::ReadAllBytes($ConfigFile)
$testBytes = [System.IO.File]::ReadAllBytes($TestFile)

$tempFile = Join-Path $env:TEMP "s3cam_test_run.py"
$stream = [System.IO.File]::OpenWrite($tempFile)
$stream.Write($cfgBytes, 0, $cfgBytes.Length)
$stream.WriteByte(10)
$stream.WriteByte(10)
$stream.Write($testBytes, 0, $testBytes.Length)
$stream.Close()

try {
    mpremote connect $Port run $tempFile
} finally {
    Remove-Item -LiteralPath $tempFile -Force -ErrorAction SilentlyContinue
}
