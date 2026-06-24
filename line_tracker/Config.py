# 小车硬件与控制参数集中配置。

# 电机供电电压，单位 V。
SUPPLY_VOLTAGE = 7.4

# 电机刚能可靠启动的等效电压，单位 V。
MOTOR_START_VOLTAGE = 4.07

# 左右轮正常巡线基础电压，单位 V。
LEFT_BASE_VOLTAGE = 5.5
RIGHT_BASE_VOLTAGE = 5.5

# 兼容旧名字，新代码优先使用 LEFT_BASE_VOLTAGE / RIGHT_BASE_VOLTAGE。
NORMAL_VOLTAGE = 5.5

# 允许输出到电机的最大等效电压，单位 V。
MAX_MOTOR_VOLTAGE = 7.4

# 普通 PID 差速修正最大幅度，单位 V。
MAX_DIFFERENTIAL_VOLTAGE = 0.5

# 是否启用大面积黑线或垂直黑线特殊策略。
ENABLE_INTERSECTION_STRATEGY = False

# 参与判断的传感器里，有这么多个判黑就认为遇到横线、交叉线或垂直黑线。
INTERSECTION_BLACK_COUNT = 4

# 遇到大面积黑线时先降速，避免直接冲过去。
LEFT_INTERSECTION_BASE_VOLTAGE = 4.8
RIGHT_INTERSECTION_BASE_VOLTAGE = 4.8

# 兼容旧名字，新代码优先使用左右分开的配置。
INTERSECTION_BASE_VOLTAGE = 4.8

# 遇到大面积黑线时额外给的强制差速，单位 V。
INTERSECTION_DIFFERENTIAL_VOLTAGE = 1.65

# 遇到大面积黑线时的转向策略。
INTERSECTION_TURN_DIRECTION = "right"

# 是否启用直角弯辅助策略。
ENABLE_CORNER_STRATEGY = True

# 当最外侧传感器或同侧多个传感器连续吃线时，使用更激进的转向电压。
CORNER_TURN_VOLTAGE = 4.8

# 直角弯时是否使用原地差速转向。True 表示一侧前进一侧后退。
CORNER_PIVOT_ENABLED = True

# 电机 PWM 频率。
PWM_FREQ = 20000

# 左电机 H 桥输入引脚。
LEFT_MOTOR_IN1 = 13
LEFT_MOTOR_IN2 = 15

# 右电机 H 桥输入引脚。
RIGHT_MOTOR_IN1 = 14
RIGHT_MOTOR_IN2 = 25

# 电机极性配置。正常为 1；如果某一侧前进方向反了，就把那一侧改成 -1。
LEFT_MOTOR_POLARITY = -1
RIGHT_MOTOR_POLARITY = 1

# 5 路灰度传感器 ADC 引脚，顺序为从左到右 1 到 5。
GRAY_SENSOR_PINS = (27, 33, 32, 35, 34)

# 灰度传感器启用开关，顺序为从左到右 1 到 5。
GRAY_SENSOR_ENABLED = (True, True, True, True, True)

# ADC 最大换算电压，仅用于调试显示。
ADC_MAX_VOLTAGE = 3.6

# 黑白判断阈值。按你的要求保持当前阈值不改。
GRAY_THRESHOLDS = (120, 100, 100, 100, 100)

# False 表示 raw 大于等于阈值时判定为黑线。
BLACK_WHEN_RAW_BELOW_THRESHOLD = False

# 灰度传感器位置权重，左负右正。
SENSOR_WEIGHTS = (-2, -1, 0, 1, 2)

# PID 参数。
KP = 0.28
KI = 0.0
KD = 0.05

# 直线稳定参数。位置在死区内时按直线处理，避免传感器轻微跳动导致左右扭。
POSITION_FILTER_ALPHA = 0.55
STRAIGHT_POSITION_DEADBAND = 0.35
STRAIGHT_CORRECTION_DEADBAND = 0.12
TURN_STRATEGY_THRESHOLD = 0.18

# 主循环周期，单位 ms。
CONTROL_PERIOD_MS = 40

# 丢线后的处理方式。直角弯时不停车，按上一次方向找线。
STOP_WHEN_LINE_LOST = False

# 丢线后原地转弯找线电压，只在 STOP_WHEN_LINE_LOST = False 时使用。
LOST_TURN_VOLTAGE = 4.6

# 兼容旧名字，新代码优先使用 LOST_TURN_VOLTAGE。
SEARCH_VOLTAGE = LOST_TURN_VOLTAGE

# 是否打印调试信息。
DEBUG_PRINT = True

# UART 接收 S3CAM 姿态数据。
# RX=GPIO22 <- S3CAM TX=GPIO45
# TX=GPIO23 -> S3CAM RX=GPIO46
UART_RX_PIN = 22
UART_TX_PIN = 23
UART_BAUDRATE = 115200
UART_TIMEOUT_MS = 500
UART_DEBUG_PRINT = False

DEBUG_PRINT_EVERY = 5

# Camera feedforward. The camera should send:
# CAM,seq,near_x,far_x,curve,quality*CRC
# near_x/far_x/curve are normalized to [-1, 1], right is positive.
ENABLE_CAMERA_FEEDFORWARD = False
CAMERA_MIN_QUALITY = 0.55
CAMERA_STRAIGHT_CURVE_THRESHOLD = 0.18
CAMERA_STRAIGHT_SPEED_GAIN = 0.12
CAMERA_CURVE_SLOWDOWN_GAIN = 0.28
CAMERA_TURN_FF_GAIN = 0.55
CAMERA_MAX_SPEED_SCALE = 1.10
CAMERA_MIN_SPEED_SCALE = 0.72

# IMU assist for camera feedforward. Keep disabled until yaw-rate damping is
# calibrated on the real track.
USE_IMU_ASSIST = False
