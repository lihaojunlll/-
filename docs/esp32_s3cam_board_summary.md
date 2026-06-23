# ESP32-S3CAM 摄像头板硬件、软件与调试问题总结

本文档整理 ESP32-S3CAM 摄像头板的硬件连接、软件结构、烧录运行方法，以及调试过程中遇到的问题和解决办法。

## 1. 板子定位

ESP32-S3CAM 板负责：

- OV3660 摄像头采集。
- 创建 Wi-Fi 热点。
- 提供浏览器摄像头页面。
- 读取 MPU6050 姿态数据。
- 通过 UART 向主控板发送姿态数据。

当前工程目录：

```text
hardware/esp32_s3cam_board/idf_camera_test
```

当前方案使用 ESP-IDF，不使用 MicroPython 摄像头模块。

## 2. 硬件连接

### 2.1 摄像头 OV3660

已验证摄像头型号：

```text
OV3660
```

已验证引脚：

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

注意：最开始使用过另一套引脚，摄像头会报 `Camera probe failed 0x106`。最终以上表为准。

### 2.2 MPU6050

MPU6050 使用独立 I2C 控制器：

| 功能 | GPIO |
| --- | ---: |
| SCL | 21 |
| SDA | 47 |
| VCC | 3.3V |
| GND | GND |

当前配置：

```c
#define I2C_MASTER_NUM     I2C_NUM_0
#define I2C_MASTER_FREQ_HZ 100000
```

地址自动尝试：

```text
0x68
0x69
```

### 2.3 UART 到主控板

摄像头板通过 UART1 发送姿态数据。

| 摄像头板 | 主控板 |
| --- | --- |
| TX GPIO45 | RX GPIO22 |
| RX GPIO46 | TX GPIO23 |
| GND | GND |

波特率：

```text
115200
```

发送格式：

```text
IMU,seq,pitch,roll,yaw
```

### 2.4 USB 串口

ESP32-S3 使用 USB-Serial/JTAG 下载和串口监视。调试中端口曾在 `COM12` 和 `COM13` 间变化，应以设备管理器或命令查询结果为准。

查询命令：

```powershell
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name
```

## 3. 软件结构

```text
hardware/esp32_s3cam_board/idf_camera_test/
  CMakeLists.txt
  deploy.ps1
  sdkconfig.defaults
  main/
    app_config.h
    main.c
    camera/
      camera_web.c
      camera_web.h
    wifi/
      wifi_ap.c
      wifi_ap.h
    imu/
      imu.c
      imu.h
    uart/
      uart_link.c
      uart_link.h
```

### 3.1 app_config.h

集中存放硬件引脚和运行参数：

- Wi-Fi 热点名称、密码。
- 摄像头引脚。
- MPU6050 I2C 引脚和频率。
- UART 引脚和波特率。
- 姿态滤波和打印周期。

### 3.2 main.c

启动顺序：

1. 初始化 NVS。
2. 初始化摄像头和 HTTP 服务。
3. 初始化 Wi-Fi AP。
4. 初始化 UART。
5. 初始化 I2C bus。
6. 挂载 MPU6050。
7. 创建 IMU 任务。

### 3.3 camera_web 模块

功能：

- 初始化 OV3660 摄像头。
- 启动 HTTP server。
- 提供网页和图像接口。

接口：

| 路径 | 作用 |
| --- | --- |
| `/` | 摄像头网页 |
| `/stream` | MJPEG 视频流 |
| `/jpg` | 单张 JPEG |

### 3.4 wifi_ap 模块

功能：

- 创建 AP 热点。
- 默认 IP 为 `192.168.4.1`。

当前配置：

```text
SSID: S3CAM
Password: 空
URL: http://192.168.4.1/
```

如果后续需要密码，在 `app_config.h` 中修改：

```c
#define WIFI_AP_PASSWORD "12345678"
```

### 3.5 imu 模块

功能：

- 读取 MPU6050。
- 计算 pitch、roll、yaw。
- 过滤读失败帧。
- 标定只统计有效样本。
- 每 `IMU_PRINT_PERIOD_MS` 打印一次日志并通过 UART 发送一次姿态。

关键配置：

```c
#define I2C_MASTER_FREQ_HZ 100000
#define CONTROL_PERIOD_MS 10
#define IMU_PRINT_PERIOD_MS 200
#define ATTITUDE_ALPHA 0.96f
```

### 3.6 uart_link 模块

功能：

- 初始化 UART1。
- 发送 IMU 数据。

输出格式：

```text
IMU,12,-0.16,1.12,0.87
```

## 4. 烧录与运行

在项目根目录运行：

```powershell
cd E:\school\class\大二下\创新认知\car
.\hardware\esp32_s3cam_board\idf_camera_test\deploy.ps1 -Port COM13
```

如果端口不是 `COM13`，用实际端口替换。

打开串口监视器：

```powershell
.\hardware\esp32_s3cam_board\idf_camera_test\deploy.ps1 -Port COM13 -Monitor
```

退出监视器：

```text
Ctrl+]
```

## 5. 浏览器访问

烧录成功并正常启动后，连接 Wi-Fi：

```text
S3CAM
```

浏览器打开：

```text
http://192.168.4.1/
```

可直接访问：

```text
http://192.168.4.1/stream
http://192.168.4.1/jpg
```

## 6. 下载模式

如果烧录时连接不上，需要手动进入下载模式：

```text
按住 BOOT
点一下 RST/EN
松开 RST/EN
等待 1 秒
松开 BOOT
```

如果串口显示：

```text
waiting for download
```

说明板子还在下载模式。不要按 BOOT，只点一下 `RST/EN` 复位即可运行应用。

## 7. 调试中遇到的问题与解决

### 7.1 MicroPython 没有 camera 模块

现象：

```text
ImportError: no module named 'camera'
```

原因：

普通 ESP32-S3 MicroPython 固件没有内置摄像头模块。

解决：

改用 ESP-IDF + `esp32-camera`。当前工程已经迁移到 ESP-IDF。

### 7.2 ESP-IDF 未安装或 idf.py 找不到

现象：

```text
idf.py not found
```

解决：

安装 Espressif ESP-IDF Installation Manager CLI，并安装 ESP-IDF v6.0.1。当前 `deploy.ps1` 会自动调用 `eim` 环境。

### 7.3 中文路径导致 CMake 崩溃

现象：

- 在 `E:\school\class\大二下\创新认知\car` 直接构建时 CMake 异常退出。

原因：

ESP-IDF/CMake 工具链在 Windows 非 ASCII 路径下不稳定。

解决：

`deploy.ps1` 会自动同步工程到：

```text
C:\Espressif\projects\s3cam_camera_test
```

然后在英文路径中构建和烧录。

### 7.4 烧录失败：No serial data received

现象：

```text
Failed to connect to ESP32-S3: No serial data received.
```

原因：

板子没有进入下载模式，或自动复位失败。

解决：

手动 BOOT + RST/EN 进入下载模式，再烧录。

### 7.5 COM 口被占用

现象：

```text
Could not open COM13
PermissionError(13, '拒绝访问。')
```

原因：

串口被 `idf_monitor.py`、Thonny、Arduino 串口监视器或其他 Python 进程占用。

解决：

```powershell
taskkill /F /IM python.exe
```

然后拔插 USB，再重新查询端口。

### 7.6 COM 口变化

现象：

```text
Serial port COM12 was not found. Available ports: ... COM13
```

原因：

进入下载模式或重新插拔后，Windows 重新枚举了端口。

解决：

查询端口并使用实际端口：

```powershell
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name
```

### 7.7 摄像头 probe 失败 0x106

现象：

```text
Detected camera not supported
Camera probe failed with error 0x106
```

原因：

摄像头引脚映射错误。最初使用的引脚表不适合当前 OV3660 板。

解决：

使用最终验证的 OV3660 引脚表：

```text
XCLK=15
D0=11 D1=9 D2=8 D3=10 D4=12 D5=18 D6=17 D7=16
VSYNC=6 HREF=7 PCLK=13 SIOD=4 SIOC=5
```

### 7.8 I2C bus already acquired

现象：

```text
I2C bus id(1) has already been acquired
ESP_ERR_INVALID_STATE
```

原因：

摄像头 SCCB/I2C 已占用 `I2C_NUM_1`，MPU6050 又尝试使用同一个 I2C 控制器。

解决：

MPU6050 改用：

```c
#define I2C_MASTER_NUM I2C_NUM_0
```

### 7.9 新旧 I2C driver 冲突

现象：

```text
CONFLICT! driver_ng is not allowed to be used with this old driver
```

原因：

摄像头驱动使用 ESP-IDF v6 新 I2C driver，MPU6050 一度改用了旧 `driver/i2c.h`，两者不能混用。

解决：

MPU6050 也使用新 driver：

```c
#include "driver/i2c_master.h"
```

### 7.10 i2c_master_probe 不兼容异步模式

现象：

```text
i2c asynchronous ... not compatible with i2c_master_probe
```

原因：

设置了 `trans_queue_depth` 后启用异步模式，和 `i2c_master_probe` 不兼容。

解决：

删除 `trans_queue_depth`，并最终不再依赖 `i2c_master_probe`。

### 7.11 MPU6050 WHO_AM_I 读出异常

现象：

```text
ESP_ERR_INVALID_RESPONSE, value=0x8A
```

原因：

一次性复合事务 `i2c_master_transmit_receive()` 在该场景下不稳定。

解决：

改成更接近 MicroPython `readfrom_mem()` 的两步读：

1. 先发送寄存器地址。
2. 延时 2ms。
3. 再读取数据。

最终能稳定读到：

```text
WHO_AM_I = 0x68
```

### 7.12 姿态数据不准、漂移明显

现象：

- 初始读失败会污染标定。
- yaw 会持续漂移。
- 日志打印太快。

解决：

- 读失败帧直接跳过。
- 标定只统计有效样本。
- I2C 降到 `100kHz`。
- IMU 计算周期保持 `10ms`。
- 串口和日志打印周期改为 `200ms`。

注意：

- yaw 只靠陀螺仪积分，长期漂移是正常现象。
- pitch/roll 由互补滤波融合加速度计和陀螺仪，短时更可靠。

### 7.13 Wi-Fi 密码显示不一致

现象：

- 页面曾显示密码 `12345678`，但代码里密码为空。

解决：

当前以 `app_config.h` 为准：

```c
#define WIFI_AP_PASSWORD ""
```

即开放热点。如果需要密码，修改该宏并同步页面说明。

## 8. 当前稳定状态

当前已验证：

- ESP-IDF v6.0.1 可编译。
- ESP32-S3 PSRAM 可用。
- OV3660 摄像头可初始化。
- 浏览器可访问摄像头网页。
- MPU6050 可读取。
- UART 可发送 IMU 姿态。
- 摄像头服务和 IMU 任务可同时运行。

推荐运行方式：

```powershell
.\hardware\esp32_s3cam_board\idf_camera_test\deploy.ps1 -Port COM13
.\hardware\esp32_s3cam_board\idf_camera_test\deploy.ps1 -Port COM13 -Monitor
```

