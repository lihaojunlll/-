param(
    [string]$Port = "COM12",
    [switch]$Monitor,
    [switch]$NoPrompt,
    [switch]$Clean
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

function Copy-IfChanged {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,
        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        return
    }

    $shouldCopy = $true
    if (Test-Path -LiteralPath $Destination) {
        $srcHash = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash
        $dstHash = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash
        $shouldCopy = $srcHash -ne $dstHash
    }

    if ($shouldCopy) {
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
    }
}

function Invoke-RobocopyMirror {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceDir,
        [Parameter(Mandatory = $true)]
        [string]$DestinationDir
    )

    New-Item -ItemType Directory -Force $DestinationDir | Out-Null
    & robocopy $SourceDir $DestinationDir /MIR /FFT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy failed with exit code $LASTEXITCODE"
    }
}

function Sync-AsciiBuildDir {
    if (-not (Test-Path "C:\Espressif")) {
        throw "C:\Espressif not found. Install ESP-IDF first."
    }

    New-Item -ItemType Directory -Force $BuildDir | Out-Null

    Copy-IfChanged -Source (Join-Path $ScriptDir "CMakeLists.txt") -Destination (Join-Path $BuildDir "CMakeLists.txt")
    Copy-IfChanged -Source (Join-Path $ScriptDir "sdkconfig.defaults") -Destination (Join-Path $BuildDir "sdkconfig.defaults")
    Copy-IfChanged -Source (Join-Path $ScriptDir "README.md") -Destination (Join-Path $BuildDir "README.md")
    Copy-IfChanged -Source (Join-Path $ScriptDir ".gitignore") -Destination (Join-Path $BuildDir ".gitignore")

    $srcMainDir = Join-Path $ScriptDir "main"
    $destMainDir = Join-Path $BuildDir "main"
    Invoke-RobocopyMirror -SourceDir $srcMainDir -DestinationDir $destMainDir

    $buildCacheDir = Join-Path $BuildDir "build"
    if ($Clean -and (Test-Path -LiteralPath $buildCacheDir)) {
        Write-Host "Cleaning build cache: $buildCacheDir"
        Remove-Item -LiteralPath $buildCacheDir -Recurse -Force
    }
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
