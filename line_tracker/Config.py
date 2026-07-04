# 小车硬件与控制参数集中配置。

# 左右轮正常巡线基础占空比 (0~1023)。
LEFT_BASE_DUTY = 950
RIGHT_BASE_DUTY = 950

# PWM 输出最大占空比。
MAX_DUTY = 1023

# PWM 输出最小占空比，非零输出不低于此值。
MIN_DUTY = 600

# 低于 MIN_DUTY 时是否反转电机。True=映射到反向, False=钳位到 MIN_DUTY。
REVERSE_ON_LOW_DUTY = True

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

# 黑白判断阈值。
GRAY_THRESHOLDS = (120, 100, 100, 100, 100)

# False 表示 raw 大于等于阈值时判定为黑线。
BLACK_WHEN_RAW_BELOW_THRESHOLD = False

# 五路传感器位置权重，用于计算偏差，左负右正。
SENSOR_WEIGHTS = (-2, -1, 0, 1, 2)

# 电机差速模式: "both"=一边加一边减, "add"=只加, "sub"=只减。
MOTOR_MODE = "sub"

# 丢线后是否停车。False 则原地转弯找线。
STOP_WHEN_LOST = False

# 丢线后原地转弯找线占空比。
LOST_TURN_DUTY = 920

# PID 参数。
KP = 250
KI = 0.0
KD = 8
# 主循环周期，单位 ms。
CONTROL_PERIOD_MS = 5

# 是否打印调试信息。
DEBUG_PRINT = True
