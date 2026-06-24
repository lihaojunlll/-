$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$PythonFiles = @(
    "main.py",
    "config.py",
    "interfaces\__init__.py",
    "interfaces\motor_driver.py",
    "interfaces\gray_sensor.py",
    "interfaces\attitude_link.py",
    "algorithms\__init__.py",
    "algorithms\line_position.py",
    "algorithms\pid.py",
    "decisions\__init__.py",
    "decisions\line_following_policy.py",
    "applications\__init__.py",
    "applications\line_tracking_app.py"
)

$PowerShellFiles = @(
    "deploy.ps1",
    "monitor.ps1"
)

foreach ($File in $PythonFiles) {
    $Path = Join-Path $ProjectDir $File
    python -B -c "import ast,sys; ast.parse(open(sys.argv[1], encoding='utf-8').read())" $Path
}

foreach ($File in $PowerShellFiles) {
    $Path = Join-Path $ProjectDir $File
    $Errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        $Path,
        [ref]$null,
        [ref]$Errors
    ) | Out-Null
    if ($Errors.Count -gt 0) {
        throw "PowerShell syntax error in $File"
    }
}

Write-Host "Syntax check passed."
