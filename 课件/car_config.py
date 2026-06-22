# 测试模式：
# - "motor"：电机电压-转速标定，结束后生成 Excel 和图像。
# - "gray"：灰度传感器 ADC 实时监视，电机保持不初始化、不转动。
# - "i2c_scan"：自动遍历 I2C 引脚组合，找出 MPU6050 接在哪两个 GPIO。
# - "mpu6050"：MPU6050 陀螺仪+加速度实时打印，需要先在 i2c_scan 找到引脚。
TEST_MODE = "i2c_scan"

# MPU6050 I2C 引脚（先用 i2c_scan 模式扫出来再填）。
MPU6050_SCL = 22
MPU6050_SDA = 21


# 电机标定配置。
SUPPLY_VOLTAGE = 7.4
PWM_FREQ = 20000
ENCODER_CPR = 600
DUTY_STEPS = range(0, 101, 5)
SETTLE_MS = 1200
MOTOR_SAMPLE_COUNT = 20
MOTOR_SAMPLE_INTERVAL_MS = 150
START_RPM = 5.0
MAX_VALID_RPM = 1000.0
START_CONFIRM_POINTS = 2
MIN_FIT_R2 = 0.8


# 灰度传感器配置。
ADC_PINS = (
    ("adc1", 27),
    ("adc2", 33),
    ("adc3", 32),
    ("adc4", 35),
    ("adc5", 34),
)
ADC_MAX_VOLTAGE = 3.6
GRAY_SAMPLE_INTERVAL_MS = 200

# ADC 原始值黑白判断阈值。
# 如果 raw <= 阈值 表示黑色，保持 GRAY_BLACK_WHEN_BELOW_THRESHOLD = True。
# 如果你的模块在黑色时输出更大的 raw 值，把它改成 False。
GRAY_THRESHOLD = 500
GRAY_BLACK_WHEN_BELOW_THRESHOLD = True
