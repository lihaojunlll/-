# ESP-IDF camera web server

This project runs an ESP32-S3CAM OV3660 camera web server through Espressif's
`esp32-camera` component. It does not use MicroPython, so it is not affected by
`ImportError: no module named 'camera'`.

Full Chinese usage and troubleshooting docs:

```text
docs/esp32_s3cam_camera_usage.md
```

## Pins

The pin map is the verified OV3660 map for this board.

| Signal | GPIO |
| --- | ---: |
| XCLK | 15 |
| PCLK | 13 |
| VSYNC | 6 |
| HREF | 7 |
| SIOD/SDA | 4 |
| SIOC/SCL | 5 |
| D0 | 11 |
| D1 | 9 |
| D2 | 8 |
| D3 | 10 |
| D4 | 12 |
| D5 | 18 |
| D6 | 17 |
| D7 | 16 |

## Build and flash

Install ESP-IDF first if `idf.py` is not available. On Windows, use one of
these two paths:

- ESP-IDF Windows Tools Installer, then open `ESP-IDF PowerShell` from the
  Start menu.
- VS Code ESP-IDF extension, then open the ESP-IDF terminal in VS Code.

In the ESP-IDF PowerShell terminal, run:

```powershell
cd E:\school\class\大二下\创新认知\car
.\hardware\esp32_s3cam_board\idf_camera_test\deploy.ps1 -Port COM13
```

On Windows, ESP-IDF/CMake may fail when the project path contains non-ASCII
characters. `deploy.ps1` automatically copies this test project to
`C:\Espressif\projects\s3cam_camera_test` before building and flashing.

Expected serial output:

```text
I (...) s3cam_web: Camera initialized
I (...) s3cam_web: Wi-Fi AP started: ssid=S3CAM password=12345678 url=http://192.168.4.1/
I (...) s3cam_web: HTTP camera server started
```

Connect a phone or computer to Wi-Fi `S3CAM` with password `12345678`, then
open:

```text
http://192.168.4.1/
```

Available endpoints:

- `/` - browser page with live stream and snapshot controls
- `/stream` - MJPEG stream
- `/jpg` - one JPEG snapshot

If `esp_camera_init` fails, check that PSRAM is available and the camera ribbon
cable is seated correctly.
