param(
    [string]$Port = "COM8",
    [int]$BaudRate = 115200
)

$ErrorActionPreference = "Stop"

Write-Host "Opening ESP32 serial monitor on $Port at $BaudRate."
Write-Host "Exit with Ctrl+C."
Write-Host ""

$SerialPort = New-Object System.IO.Ports.SerialPort $Port, $BaudRate, None, 8, one
$SerialPort.Encoding = [System.Text.Encoding]::ASCII
$SerialPort.ReadTimeout = 200

try {
    $SerialPort.Open()
    while ($true) {
        try {
            $Text = $SerialPort.ReadExisting()
            if ($Text.Length -gt 0) {
                Write-Host -NoNewline $Text
            }
        }
        catch [System.TimeoutException] {
        }
        Start-Sleep -Milliseconds 20
    }
}
finally {
    if ($SerialPort.IsOpen) {
        $SerialPort.Close()
    }
}
