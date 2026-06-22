param(
    [string]$Port = "COM8"
)

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
$CalibrationFile = Join-Path $ProjectDir "motor_calibration.py"
$ConfigFile = Join-Path $ProjectDir "car_config.py"

if (-not (Test-Path -LiteralPath $CalibrationFile)) {
    throw "Calibration file not found: $CalibrationFile"
}

if (-not (Test-Path -LiteralPath $ConfigFile)) {
    throw "Config file not found: $ConfigFile"
}

if (-not (Get-Command mpremote -ErrorAction SilentlyContinue)) {
    throw "mpremote not found. Run: python -m pip install mpremote"
}

$ModeLine = Select-String -LiteralPath $ConfigFile -Pattern '^\s*TEST_MODE\s*=\s*"([^"]+)"' |
    Select-Object -First 1
if (-not $ModeLine) {
    throw 'TEST_MODE not found in car_config.py'
}
$TestMode = $ModeLine.Matches[0].Groups[1].Value.ToLower()

Write-Host "Current TEST_MODE: $TestMode"
if ($TestMode -eq "motor") {
    Write-Host "Lift the car so both wheels can rotate freely."
    Write-Host "Running motor voltage-speed calibration on $Port..."
    Write-Host "Press Ctrl+C to stop and release the motors."
}
elseif ($TestMode -eq "gray") {
    Write-Host "Running grayscale sensor monitor on $Port..."
    Write-Host "Motors will not be initialized."
    Write-Host "Press Ctrl+C to stop the gray sensor monitor."
}
elseif ($TestMode -eq "i2c_scan") {
    Write-Host "Running I2C pin scanner on $Port..."
    Write-Host "Motors will not be initialized."
}
elseif ($TestMode -eq "mpu6050") {
    Write-Host "Running MPU6050 monitor on $Port..."
    Write-Host "Motors will not be initialized."
    Write-Host "Press Ctrl+C to stop the MPU6050 monitor."
}
elseif ($TestMode -eq "uart_recv") {
    Write-Host "Running UART receive debug on $Port..."
    Write-Host "Motors will not be initialized."
    Write-Host "Press Ctrl+C to stop and print stats."
}
else {
    throw "Unknown TEST_MODE: $TestMode"
}
Write-Host ""

$ResultRoot = Join-Path $ProjectDir "calibration_results"
$Timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$ResultDir = Join-Path $ResultRoot $Timestamp
New-Item -ItemType Directory -Path $ResultDir -Force | Out-Null
$LogFile = Join-Path $ResultDir "calibration_raw_log.txt"

Write-Host "Stopping any running program on $Port..."
mpremote connect $Port soft-reset 2>&1 | Out-Null
Start-Sleep -Seconds 3

& mpremote connect $Port cp $ConfigFile :car_config.py
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upload car_config.py. Check the port and serial usage."
}

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$LogStream = New-Object System.IO.FileStream(
    $LogFile,
    [System.IO.FileMode]::Create,
    [System.IO.FileAccess]::Write,
    [System.IO.FileShare]::Read
)
$LogWriter = New-Object System.IO.StreamWriter($LogStream, $Utf8NoBom)
$LogWriter.AutoFlush = $true

try {
    & mpremote connect $Port run $CalibrationFile 2>&1 | ForEach-Object {
        $Line = "$_"
        Write-Host $Line
        $LogWriter.WriteLine($Line)
    }
    $CalibrationExitCode = $LASTEXITCODE
}
finally {
    $LogWriter.Dispose()
    $LogStream.Dispose()
}

if ($CalibrationExitCode -ne 0) {
    throw "Calibration failed. Check the port, wiring, and serial-port usage."
}

if ($TestMode -ne "motor") {
    Write-Host ""
    Write-Host "Raw log saved: $LogFile"
    return
}

$ReportBuilder = Join-Path $ProjectDir "build_calibration_report.mjs"
$RuntimeRoot = "C:\Users\17991\.cache\codex-runtimes\codex-primary-runtime\dependencies"
$NodeExe = Join-Path $RuntimeRoot "node\bin\node.exe"
$NodePackages = Join-Path $RuntimeRoot "node\node_modules"
$ExcelFile = Join-Path $ResultDir "motor_voltage_speed_calibration.xlsx"
$PreviewFile = Join-Path $ResultDir "motor_voltage_speed_chart.png"
$RuntimeDir = Join-Path $env:TEMP "car-calibration-report"
$RuntimeNodeModules = Join-Path $RuntimeDir "node_modules"
$RuntimeBuilder = Join-Path $RuntimeDir "build_calibration_report.mjs"

if (-not (Test-Path -LiteralPath $ReportBuilder)) {
    throw "Report builder not found: $ReportBuilder"
}
if (-not (Test-Path -LiteralPath $NodeExe)) {
    throw "Codex spreadsheet runtime not found: $NodeExe"
}
if (-not (Test-Path -LiteralPath $NodePackages)) {
    throw "Codex spreadsheet packages not found: $NodePackages"
}

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
if (-not (Test-Path -LiteralPath $RuntimeNodeModules)) {
    New-Item -ItemType Junction -Path $RuntimeNodeModules -Target $NodePackages |
        Out-Null
}
Copy-Item -LiteralPath $ReportBuilder -Destination $RuntimeBuilder -Force

Write-Host ""
Write-Host "Generating Excel workbook and chart..."
& $NodeExe $RuntimeBuilder `
    --input $LogFile `
    --output $ExcelFile `
    --preview $PreviewFile

if ($LASTEXITCODE -ne 0) {
    throw "Calibration completed, but Excel report generation failed. Raw log: $LogFile"
}

$InspectFile = "$ExcelFile.inspect.ndjson"
if (Test-Path -LiteralPath $InspectFile) {
    Remove-Item -LiteralPath $InspectFile -Force
}

Write-Host ""
Write-Host "Calibration results saved:"
Write-Host "  Excel: $ExcelFile"
Write-Host "  Chart: $PreviewFile"
Write-Host "  Raw log: $LogFile"
