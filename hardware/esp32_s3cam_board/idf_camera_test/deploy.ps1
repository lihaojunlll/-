param(
    [string]$Port = "COM12",
    [switch]$Monitor,
    [switch]$NoPrompt
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Eim = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\Espressif.EIM-CLI_Microsoft.Winget.Source_8wekyb3d8bbwe\eim.exe"
$BuildDir = "C:\Espressif\projects\s3cam_camera_test"

function Invoke-Idf {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command
    )

    if (Get-Command idf.py -ErrorAction SilentlyContinue) {
        Invoke-Expression $Command
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed: $Command"
        }
        return
    }

    if (Test-Path -LiteralPath $Eim) {
        & $Eim run $Command
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed: $Command"
        }
        return
    }

    throw @"
idf.py not found.

Install ESP-IDF first, then open an ESP-IDF PowerShell terminal and rerun this script.

Recommended:
1. Install ESP-IDF Windows Tools Installer.
2. Open "ESP-IDF PowerShell" from the Start menu.
3. cd to this folder:
   cd <your-car-project>\hardware\esp32_s3cam_board\idf_camera_test
4. Run:
   .\deploy.ps1 -Port $Port

If you use the VS Code ESP-IDF extension, open the ESP-IDF Terminal there and run the same command.
"@
}

function Sync-AsciiBuildDir {
    if (-not (Test-Path "C:\Espressif")) {
        throw "C:\Espressif not found. Install ESP-IDF first."
    }

    New-Item -ItemType Directory -Force $BuildDir | Out-Null
    New-Item -ItemType Directory -Force (Join-Path $BuildDir "main") | Out-Null

    Copy-Item -LiteralPath (Join-Path $ScriptDir "CMakeLists.txt") -Destination $BuildDir -Force
    Copy-Item -LiteralPath (Join-Path $ScriptDir "sdkconfig.defaults") -Destination $BuildDir -Force
    Copy-Item -LiteralPath (Join-Path $ScriptDir "README.md") -Destination $BuildDir -Force
    Copy-Item -LiteralPath (Join-Path $ScriptDir ".gitignore") -Destination $BuildDir -Force -ErrorAction SilentlyContinue
    $srcMainDir = Join-Path $ScriptDir "main"
    Copy-Item -LiteralPath (Join-Path $srcMainDir "*") -Destination (Join-Path $BuildDir "main") -Recurse -Force
}

function Assert-PortExists {
    $ports = @(Get-CimInstance Win32_SerialPort | Select-Object -ExpandProperty DeviceID)
    if ($ports -notcontains $Port) {
        $available = if ($ports.Count -gt 0) { $ports -join ", " } else { "(none)" }
        throw "Serial port $Port was not found. Available ports: $available"
    }
}

Sync-AsciiBuildDir

Push-Location $BuildDir
try {
    Write-Host "Building ESP32-S3 camera test in $BuildDir..."
    if (-not (Test-Path -LiteralPath (Join-Path $BuildDir "sdkconfig"))) {
        Invoke-Idf "idf.py set-target esp32s3"
    }
    Invoke-Idf "idf.py -p $Port build"

    Write-Host ""
    Write-Host "Ready to flash $Port."
    Write-Host "If your board needs manual download mode: hold BOOT, tap RST/EN, release RST/EN, then release BOOT."
    if (-not $NoPrompt) {
        Read-Host "Press Enter after the board is connected and ready"
    }
    Assert-PortExists
    Write-Host ""
    $oldEspBaud = $env:ESPBAUD
    $env:ESPBAUD = "115200"
    try {
        Invoke-Idf "idf.py -p $Port flash"
    } finally {
        $env:ESPBAUD = $oldEspBaud
    }

    if ($Monitor) {
        Write-Host ""
        Write-Host "Opening ESP-IDF serial monitor. Press Ctrl+] to exit."
        Write-Host ""
        Invoke-Idf "idf.py -p $Port monitor"
    }
} finally {
    Pop-Location
}
