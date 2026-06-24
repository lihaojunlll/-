# 寻迹车摄像头与 MPU6050 融合策略

本文档说明如何把 ESP32-S3 摄像头板上的摄像头和 MPU6050 用到主控寻迹车上，以及当前串口通信协议。

## 总体原则

当前建议采用“三层控制”：

1. 灰度传感器做反馈控制，负责让车实时贴住黑线。
2. 摄像头做前馈控制，负责提前判断直道、弯道、圆弧和路口。
3. MPU6050 做运动响应辅助，负责判断车身是否真的按预期转起来。

核心思路是：灰度管“现在脚下的线”，摄像头管“前面马上要来的路”，MPU6050 管“车身实际有没有跟上”。

## 推荐控制策略

### 阶段 1：灰度反馈 + 摄像头前馈

这是最适合这条赛道的主策略。

主控板继续按 5 路灰度传感器计算黑线位置，PID 输出基础差速。摄像头板提前识别前方路线，并通过 UART 发送：

```text
CAM,seq,near_x,far_x,curve,quality*CRC
```

主控根据摄像头前馈做两件事：

- 前方是直道：提高基础速度。
- 前方是弯道或圆弧：提前降低基础速度，并叠加转向前馈。

控制形式：

```text
left  = left_base  * speed_scale + gray_pid + camera_turn_ff
right = right_base * speed_scale - gray_pid - camera_turn_ff
```

其中：

- `speed_scale > 1.0` 表示直道加速。
- `speed_scale < 1.0` 表示弯道提前减速。
- `camera_turn_ff > 0` 表示提前右转。
- `camera_turn_ff < 0` 表示提前左转。

这一阶段要确认：

- UART 数据稳定，`bad=0` 或极少。
- `lost` 不持续增加。
- 摄像头看到直道时 `curve` 接近 0。
- 摄像头看到右弯时 `curve` 为正。
- 摄像头看到左弯时 `curve` 为负。
- 摄像头看不清时 `quality` 降低，主控自动退回灰度 PID。

### 阶段 2：MPU6050 辅助弯道

MPU6050 不适合直接看路线，但适合判断车有没有真的转起来。

建议用法：

- 摄像头判断前方右弯，主控给右转前馈。
- MPU6050 的 yaw 应该开始向右变化。
- 如果 yaw 变化太小，说明转向不够，可以略微增加转向前馈。
- 如果 yaw 变化过快，说明转得太猛，可以减小前馈或继续降速。

这相当于给摄像头前馈加一个动态校验，避免只看图像但车身实际没转过去。

### 阶段 3：直道加速

摄像头判断前方一段距离内黑线基本直，且灰度传感器也稳定在线上时，可以加速。

建议条件：

- `quality >= CAMERA_MIN_QUALITY`
- `abs(curve) < CAMERA_STRAIGHT_CURVE_THRESHOLD`
- 灰度黑线位置稳定，没有频繁丢线

加速不应该太猛。当前配置：

```python
CAMERA_STRAIGHT_SPEED_GAIN = 0.12
CAMERA_MAX_SPEED_SCALE = 1.10
```

意思是最多把基础速度提高到 1.10 倍。

### 阶段 4：弯道和圆弧提前减速

摄像头判断前方曲率变大时，主控提前降低基础速度。

当前配置：

```python
CAMERA_CURVE_SLOWDOWN_GAIN = 0.28
CAMERA_MIN_SPEED_SCALE = 0.72
```

意思是弯越急，速度越低，最低降到基础速度的 0.72 倍。

### 阶段 5：摄像头算法

摄像头建议先做低分辨率黑线识别：

1. 取图像下半部分作为近处 ROI，得到 `near_x`。
2. 取图像中上部分作为远处 ROI，得到 `far_x`。
3. 用 `far_x - near_x` 和黑线方向估算 `curve`。
4. 根据黑线像素数量和连续性估算 `quality`。

归一化约定：

- 图像中心为 0。
- 左侧为负，右侧为正。
- 范围限制在 `[-1, 1]`。
- `quality` 范围为 `[0, 1]`。

## 当前 UART 通信

### 接线

摄像头板到主控板：

- 摄像头板 TX GPIO45 -> 主控板 RX GPIO22
- 摄像头板 RX GPIO46 -> 主控板 TX GPIO23
- GND 必须共地
- 波特率 115200

### IMU 数据包

摄像头板发送：

```text
IMU,seq,pitch,roll,yaw*CRC
```

示例：

```text
IMU,123,-0.15,1.26,1.02*5A
```

说明：

- `seq`：递增序号，用于发现丢包。
- `pitch`：俯仰角，单位度。
- `roll`：横滚角，单位度。
- `yaw`：偏航角，单位度。
- `CRC`：对 `*` 前面的正文做逐字节异或校验，两位十六进制。

主控端兼容旧格式：

```text
IMU,seq,pitch,roll,yaw
```

但正式调车建议使用带 `*CRC` 的新格式。

### Camera 前馈包

摄像头板发送：

```text
CAM,seq,near_x,far_x,curve,quality*CRC
```

示例：

```text
CAM,42,0.05,0.02,0.03,0.91*2A
CAM,43,0.10,0.55,0.70,0.86*31
```

说明：

- `near_x`：近处黑线中心偏移，右正左负。
- `far_x`：远处黑线中心偏移，右正左负。
- `curve`：前方曲率或转向趋势，右弯为正，左弯为负。
- `quality`：识别可信度，低于阈值时主控忽略摄像头。

### 主控端状态

主控端会维护这些状态：

- `fresh`：最近 500 ms 内是否收到有效数据。
- `seq`：最后收到的序号。
- `pitch, roll, yaw`：最近姿态。
- `lost_packets`：根据序号推算的丢包数量。
- `bad_packets`：格式错误或校验失败数量。
- `cam_fresh`：最近是否收到摄像头前馈。
- `cam_near, cam_far, cam_curve, cam_quality`：最近摄像头前馈。

调试打印中会看到：

```text
imu=fresh,seq,pitch,roll,yaw cam=fresh,seq,near,far,curve,quality lost=imu_lost,cam_lost,bad=...
```

例如：

```text
imu=1,123,-0.1,1.2,3.4 cam=1,42,0.05,0.02,0.03,0.91 lost=0,0,bad=0
```

## 当前代码开关

主控配置在 `line_tracker/Config.py`：

```python
UART_TIMEOUT_MS = 500
UART_DEBUG_PRINT = False
DEBUG_PRINT_EVERY = 5
USE_IMU_ASSIST = False
```

当前 `USE_IMU_ASSIST` 先保留为关闭。下一步如果要真正融合控制，建议先只做“丢线时限制转角”，风险最小。

## 调车顺序

1. 只烧录摄像头板，确认网页和 IMU 正常。
2. 只烧录主控板，不接摄像头板，确认灰度寻迹正常。
3. 接 UART 和 GND，主控打印中确认 `imu=1`。
4. 手动转动车身，看 yaw 是否变化，`bad` 是否增加。
5. 低速跑直线，记录 yaw 漂移。
6. 再考虑打开 IMU 辅助策略。

## 常见问题

### 主控一直显示 `imu=0`

说明没有收到新数据或数据超时。

检查：

- TX/RX 是否交叉连接。
- GND 是否共地。
- 两边波特率是否都是 115200。
- 摄像头板是否正在运行 ESP-IDF 程序。

### `bad` 一直增加

说明串口数据损坏或格式不匹配。

检查：

- 串口线是否太长或接触不良。
- 是否同时有别的程序在往同一个 UART 发数据。
- 摄像头板和主控板是否都已更新到当前协议。

### `lost` 一直增加

说明主控收到数据，但中间漏了包。

可能原因：

- 主控打印太频繁。
- 控制循环里做了耗时操作。
- 摄像头板发送频率太高。

当前已经把摄像头板 IMU 发送周期设为 200 ms，主控调试打印也可通过 `DEBUG_PRINT_EVERY` 降频。
