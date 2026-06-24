# ESP32-S3CAM 摄像头使用与控制说明

本文档说明本项目中 ESP32-S3CAM 摄像头板的烧录、启动、网页访问和常见故障处理。

## 当前方案

摄像头部分使用 ESP-IDF 实现，不再使用 MicroPython 的 `camera` 模块。

原因：

- 普通 MicroPython ESP32-S3 固件没有内置 `camera` 模块。
- 本板摄像头已经验证为 OV3660。
- ESP-IDF + `esp32-camera` 已经验证可正常初始化、抓帧和提供网页访问。

当前程序位置：

```text
hardware/esp32_s3cam_board/idf_camera_test
```

烧录后，开发板会创建 Wi-Fi 热点，并提供摄像头网页。

```text
Wi-Fi 名称: S3CAM
Wi-Fi 密码: 12345678
访问地址: http://192.168.4.1/；
```

## 已验证摄像头引脚

本板使用 OV3660 摄像头，已验证引脚如下。

| 信号 | GPIO |
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

如果使用其他引脚，可能出现：

```text
Detected camera not supported
Camera probe failed with error 0x106
```

## 烧录命令

在项目根目录运行：

```powershell
cd E:\school\class\大二下\创新认知\car
.\hardware\esp32_s3cam_board\idf_camera_test\deploy.ps1 -Port COM13
```

如果端口不是 `COM13`，先查看当前串口：

```powershell
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name
```

然后把命令里的端口改成实际端口，例如：

```powershell
.\hardware\esp32_s3cam_board\idf_camera_test\deploy.ps1 -Port COM12
```

## 进入下载模式

如果烧录时卡在 `Connecting...` 或提示收不到串口数据，需要手动进入下载模式。

操作顺序：

```text
按住 BOOT
点一下 RST/EN
松开 RST/EN
等待 1 秒
松开 BOOT
```

如果进入下载模式后端口号变化，例如 `COM12` 变成 `COM13`，重新用新的端口烧录。

## 启动和访问网页

烧录成功后，串口会显示：

```text
Hard resetting via RTS pin...
Done
```

如果板子停在下载模式：

```text
waiting for download
```

不要按 BOOT，只点一下 `RST/EN` 复位。

启动成功后，用手机或电脑连接 Wi-Fi：

```text
S3CAM
12345678
```

然后浏览器打开：

```text
http://192.168.4.1/
```

## 网页接口

程序提供三个 HTTP 接口。

| 路径 | 作用 |
| --- | --- |
| `/` | 摄像头网页，包含视频流和抓拍按钮 |
| `/stream` | MJPEG 视频流 |
| `/jpg` | 单张 JPEG 抓拍 |

示例：

```text
http://192.168.4.1/
http://192.168.4.1/stream
http://192.168.4.1/jpg
```

## 查看串口日志

如果需要看摄像头初始化、Wi-Fi 热点和 HTTP 服务日志：

```powershell
cd E:\school\class\大二下\创新认知\car
.\hardware\esp32_s3cam_board\idf_camera_test\deploy.ps1 -Port COM13 -Monitor
```

退出串口监视器：

```text
Ctrl+]
```

正常日志应包含：

```text
sensor PID=0x3660
Camera initialized
Wi-Fi AP started: ssid=S3CAM password=12345678 url=http://192.168.4.1/
HTTP camera server started
```

## 常见问题

### idf.py 找不到

普通 PowerShell 里可能没有 `idf.py`。本项目的 `deploy.ps1` 会自动调用 ESP-IDF Installation Manager 的 `eim` 环境，一般不需要手动打开 ESP-IDF PowerShell。

直接使用项目脚本：

```powershell
.\hardware\esp32_s3cam_board\idf_camera_test\deploy.ps1 -Port COM13
```

### COM 口被占用

错误示例：

```text
Could not open COM13, the port is busy or doesn't exist.
PermissionError(13, '拒绝访问。')
```

处理：

```powershell
taskkill /F /IM python.exe
```

然后拔掉 USB，等待 2 秒，再插回去。

也要关闭：

- Thonny
- Arduino 串口监视器
- `mpremote`
- 其他 ESP-IDF monitor 终端

### 烧录时端口消失

错误示例：

```text
FileNotFoundError
Could not open COM13
```

这是复位或进入下载模式时 USB 串口重新枚举导致的。重新查询端口：

```powershell
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name
```

如果端口变了，用新端口重新烧录。

### 一直显示 waiting for download

说明板子还停在下载模式。

处理：

```text
不要按 BOOT
只点一下 RST/EN
```

如果每次复位都进入下载模式，检查 BOOT/IO0 按键是否卡住，或 IO0 是否被外部电路拉低。

### Camera probe failed 0x106

这个错误通常是摄像头型号或引脚不对。本项目已经验证本板是 OV3660，并使用上文的引脚表。

如果重新出现该错误，检查：

- 摄像头排线是否插紧
- 是否烧录的是最新工程
- 是否误改了 `main.c` 中的摄像头引脚

## 后续控制扩展

当前程序只负责摄像头网页访问。后续如果要把摄像头和小车控制合并，可以在网页中继续增加控制接口，例如：

| 路径 | 作用 |
| --- | --- |
| `/cmd?move=forward` | 前进 |
| `/cmd?move=backward` | 后退 |
| `/cmd?move=left` | 左转 |
| `/cmd?move=right` | 右转 |
| `/cmd?move=stop` | 停止 |

摄像头视频流继续使用：

```text
http://192.168.4.1/stream
```

小车控制可以使用 HTTP 请求触发电机控制逻辑。
