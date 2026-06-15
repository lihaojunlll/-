class MotorConfig:
    """电机、编码器及 PWM 硬件配置。"""

    # 左右电机驱动模块的方向控制引脚。
    LEFT_IN1 = 13
    LEFT_IN2 = 15
    RIGHT_IN1 = 14
    RIGHT_IN2 = 25

    # 左右电机编码器的 A、B 相输入引脚。
    LEFT_ENCODER_A = 16
    LEFT_ENCODER_B = 17
    RIGHT_ENCODER_A = 18
    RIGHT_ENCODER_B = 19

    PWM_FREQUENCY = 20000

    # 电机安装方向修正系数，只能设置为 1 或 -1。
    # 当前左电机接线方向与逻辑方向相反，因此左轮取 -1。
    LEFT_DIRECTION = 1
    RIGHT_DIRECTION = -1


class TractionConfig:
    """五路灰度传感器硬件配置。"""

    # 引脚顺序必须与传感器空间顺序一致：最左侧 -> 最右侧。
    ADC_PINS = (27, 33, 32, 35, 34)


class AlgorithmConfig:
    """算法层参数配置。"""

    # 灰度循迹使用的 PID 参数。
    TRACKING_KP = 18.0
    TRACKING_KI = 0.0
    TRACKING_KD = 8.0

    # PID 输出及积分项限幅，用于抑制过大控制量和积分饱和。
    PID_OUTPUT_LIMITS = (-100.0, 100.0)
    PID_INTEGRAL_LIMITS = (-20.0, 20.0)


class PolicyConfig:
    """循迹策略参数配置。"""

    # 五个传感器可在标定后分别设置黑白判断阈值。
    THRESHOLDS = (2000, 2000, 2000, 2000, 2000)

    # True 表示数值高于阈值时检测到黑线，False 表示低于阈值时检测到黑线。
    BLACK_IS_HIGH = False

    # 各种行驶状态使用的速度百分比。
    BASE_SPEED = 40
    MAX_SPEED = 75
    SEARCH_SPEED = 28
    INTERSECTION_SPEED = 32

class AppConfig:
    """应用调度层配置。"""

    # 控制循环周期和串口调试输出周期，单位均为毫秒。
    CONTROL_INTERVAL_MS = 20
    DEBUG_INTERVAL_MS = 200



    # 电机诊断测试参数。
    MOTOR_TEST_SPEED = 70
    MOTOR_TEST_START_DELAY_MS = 5000
    MOTOR_TEST_DURATION_MS = 3000
    MOTOR_TEST_PAUSE_MS = 1000

    # 运行模式可选："sensor_test"、"motor_test" 或 "tracking"。
    RUN_MODE = "tracking"
