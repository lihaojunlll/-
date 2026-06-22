# ESP32-S3CAM 板资料

## 引脚分配

| 功能 | GPIO |
|------|------|
| 左电机 IN1 | GPIO13 |
| 左电机 IN2 | GPIO15 |
| 右电机 IN1 | GPIO14 |
| 右电机 IN2 | GPIO25 |
| 灰度传感器 1 (最左) | GPIO27 |
| 灰度传感器 2 | GPIO33 |
| 灰度传感器 3 (中间) | GPIO32 |
| 灰度传感器 4 | GPIO35 |
| 灰度传感器 5 (最右) | GPIO34 |
| MPU6050 SCL | GPIO21 |
| MPU6050 SDA | GPIO47 |

## I2C 初始化

```python
from machine import I2C, Pin
i2c = I2C(0, scl=Pin(21), sda=Pin(47), freq=400000)
```

## 注意

本板 I2C 引脚为 SCL=GPIO21、SDA=GPIO47，与标准 ESP32 默认不同（标准为 GPIO18/19 或 GPIO22/21）。
