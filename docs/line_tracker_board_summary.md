# 循迹小车主控板硬件、软件与调试问题总结

本文档整理循迹小车主控板的硬件连接、软件结构、运行方式和调试过程中遇到的问题。

## 1. 板子定位

循迹小车主控板负责：

- 读取 5 路灰度传感器。
- 计算黑线位置。
- 使用 PID 生成左右轮差速。
- 控制左右直流电机。
- 通过 UART 接收 ESP32-S3CAM 板发送的姿态数据。

当前代码目录：

```text
line_tracker
```

主要入口：

```text
line_tracker/main.py
line_tracker/Config.py
```

## 2. 硬件连接

### 2.1 电机驱动

左右电机通过 H 桥输入脚控制，PWM 频率为 `20000 Hz`。

| 功能 | GPIO |
| --- | ---: |
| 左电机 IN1 | 13 |
| 左电机 IN2 | 15 |
| 右电机 IN1 | 14 |
| 右电机 IN2 | 25 |

电机参数：

| 参数 | 当前值 |
| --- | ---: |
| 电机供电电压 | 7.4 V |
| 起转电压 | 4.07 V |
| 左轮基础电压 | 5.5 V |
| 右轮基础电压 | 5.5 V |
| 最大输出电压 | 7.4 V |
| 最大差速修正 | 0.7 V |

电机极性：

```python
LEFT_MOTOR_POLARITY = -1
RIGHT_MOTOR_POLARITY = 1
```

如果某一侧电机前进方向反了，优先修改极性配置，不要改接线逻辑。

### 2.2 灰度传感器

5 路灰度传感器从左到右接入：

| 序号 | 位置 | GPIO |
| --- | --- | ---: |
| 1 | 最左 | 27 |
| 2 | 左中 | 33 |
| 3 | 中间 | 32 |
| 4 | 右中 | 35 |
| 5 | 最右 | 34 |

配置位置：

```text
line_tracker/Config.py
```

当前阈值：

```python
GRAY_THRESHOLDS = (100, 100, 100, 100, 100)
BLACK_WHEN_RAW_BELOW_THRESHOLD = False
```

含义：raw 大于等于阈值时判定为黑线。

传感器权重：

```python
SENSOR_WEIGHTS = (-2, -1, 0, 1, 2)
```

左侧为负，右侧为正。

### 2.3 与摄像头板 UART 通信

主控板接收 ESP32-S3CAM 板发送的 IMU 姿态数据。

主控板配置：

```python
UART_RX_PIN = 22
UART_TX_PIN = 23
UART_BAUDRATE = 115200
```

推荐接线：

| 主控板 | 摄像头板 |
| --- | --- |
| RX GPIO22 | TX GPIO45 |
| TX GPIO23 | RX GPIO46 |
| GND | GND |

注意：UART 必须共地。

## 3. 软件结构

```text
line_tracker/
  main.py
  Config.py
  algorithms/
    line_position.py
    pid.py
  applications/
    line_tracking_app.py
  decisions/
    line_following_policy.py
  interfaces/
    gray_sensor.py
    motor_driver.py
  deploy.ps1
  monitor.ps1
  run_local_syntax_check.ps1
```

### 3.1 主入口

`main.py` 负责创建完整应用：

- `GraySensorArray`：读取灰度传感器。
- `VoltageMotor`：电机电压到 PWM 占空比转换。
- `DifferentialDrive`：左右轮差速驱动。
- `LinePositionEstimator`：根据黑线状态估计偏移。
- `PIDController`：计算差速修正。
- `LineFollowingPolicy`：处理直线、丢线、交叉线、直角弯等策略。
- `LineTrackingApp`：主循环。

### 3.2 控制周期

```python
CONTROL_PERIOD_MS = 40
```

即主控板约 25Hz 控制电机。

### 3.3 PID 参数

```python
KP = 0.35
KI = 0.0
KD = 0.12
```

如果小车左右摆动明显，优先降低 `KP` 或 `KD`。

如果转弯不够灵敏，优先提高 `KP` 或 `MAX_DIFFERENTIAL_VOLTAGE`。

### 3.4 丢线与直角弯策略

丢线不停车，按上一次方向找线：

```python
STOP_WHEN_LINE_LOST = False
LOST_TURN_VOLTAGE = 5.2
```

直角弯辅助已开启：

```python
ENABLE_CORNER_STRATEGY = True
CORNER_TURN_VOLTAGE = 4.8
CORNER_PIVOT_ENABLED = True
```

交叉线策略当前关闭：

```python
ENABLE_INTERSECTION_STRATEGY = False
```

## 4. 部署和运行

在项目根目录运行：

```powershell
cd E:\school\class\大二下\创新认知\car
.\line_tracker\deploy.ps1 -Port COM口
```

如果要打开串口监视器：

```powershell
.\line_tracker\monitor.ps1 -Port COM口
```

也可以先做本地语法检查：

```powershell
.\line_tracker\run_local_syntax_check.ps1
```

## 5. 调试中遇到的问题与解决

### 5.1 中文路径或编码显示乱码

现象：

- PowerShell 输出中中文注释显示乱码。
- 文件内容不影响程序运行，但阅读不方便。

原因：

- Windows 控制台编码和文件编码不一致。

处理：

- 关键配置尽量用变量名和表格说明。
- 文档使用 UTF-8 保存。
- 程序逻辑不要依赖中文字符串。

### 5.2 电机低电压不转

现象：

- PWM 有输出，但电机只响或发热，不转动。

原因：

- 直流电机存在起转电压。

处理：

代码中使用 `MOTOR_START_VOLTAGE = 4.07`，非零输出会自动抬到起转电压。

### 5.3 电机方向相反

现象：

- 程序给前进指令，但某侧电机反转。

处理：

修改：

```python
LEFT_MOTOR_POLARITY = -1
RIGHT_MOTOR_POLARITY = 1
```

不要优先改控制算法。

### 5.4 灰度传感器黑白判断反了

现象：

- 黑线被判成白底，白底被判成黑线。

处理：

修改：

```python
BLACK_WHEN_RAW_BELOW_THRESHOLD = False
```

当前配置表示 raw 大于等于阈值为黑线。

### 5.5 直角弯容易丢线

现象：

- 小车遇到急弯时冲出线。

处理：

已开启直角弯策略：

```python
ENABLE_CORNER_STRATEGY = True
CORNER_PIVOT_ENABLED = True
CORNER_TURN_VOLTAGE = 4.8
```

如果仍然冲出，降低基础电压或提高直角弯转向电压。

### 5.6 串口端口变化

现象：

- 烧录脚本提示指定 COM 口不存在。

处理：

查询端口：

```powershell
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name
```

再把 `-Port` 改为实际端口。

### 5.7 UART 姿态数据收不到

检查：

- 主控 RX 是否接摄像头板 TX。
- 主控 TX 是否接摄像头板 RX。
- 两块板是否共地。
- 波特率是否都是 `115200`。

摄像头板发送格式：

```text
IMU,seq,pitch,roll,yaw
```

## 6. 当前稳定配置建议

| 项目 | 建议 |
| --- | --- |
| 基础速度 | 先用 5.5 V，稳定后再提高 |
| 控制周期 | 40 ms |
| 灰度阈值 | 先保持 100，再按现场光照调 |
| PID | 先保持 KP=0.35, KD=0.12 |
| 调试输出 | 调车时打开，比赛/演示时可关闭 |

