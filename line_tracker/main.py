import config
from algorithms.line_position import LinePositionEstimator
from algorithms.pid import PIDController
from applications.line_tracking_app import LineTrackingApp
from decisions.line_following_policy import LineFollowingPolicy
from interfaces.attitude_link import AttitudeLink
from interfaces.ble_debug import BLEDebug
from interfaces.gray_sensor import GraySensorArray
from interfaces.motor_driver import DifferentialDrive, VoltageMotor
from interfaces.wifi_setup import connect as wifi_connect, start_webrepl


def build_app():
    """创建正式寻迹应用。"""
    sensors = GraySensorArray(
        pins=config.GRAY_SENSOR_PINS,
        thresholds=config.GRAY_THRESHOLDS,
        black_when_below=config.BLACK_WHEN_RAW_BELOW_THRESHOLD,
        max_voltage=config.ADC_MAX_VOLTAGE,
        enabled_mask=config.GRAY_SENSOR_ENABLED,
    )

    left_motor = VoltageMotor(
        config.LEFT_MOTOR_IN1,
        config.LEFT_MOTOR_IN2,
        config.PWM_FREQ,
        config.SUPPLY_VOLTAGE,
        config.MOTOR_START_VOLTAGE,
        config.MAX_MOTOR_VOLTAGE,
        config.LEFT_MOTOR_POLARITY,
    )
    right_motor = VoltageMotor(
        config.RIGHT_MOTOR_IN1,
        config.RIGHT_MOTOR_IN2,
        config.PWM_FREQ,
        config.SUPPLY_VOLTAGE,
        config.MOTOR_START_VOLTAGE,
        config.MAX_MOTOR_VOLTAGE,
        config.RIGHT_MOTOR_POLARITY,
    )
    drive = DifferentialDrive(left_motor, right_motor)

    position_estimator = LinePositionEstimator(config.SENSOR_WEIGHTS)
    pid_controller = PIDController(
        config.KP,
        config.KI,
        config.KD,
        config.MAX_DIFFERENTIAL_VOLTAGE,
    )
    pid_circular = PIDController(
        config.KP_CIRCULAR,
        config.KI_CIRCULAR,
        config.KD_CIRCULAR,
        config.MAX_DIFFERENTIAL_VOLTAGE_CIRCULAR,
    )
    policy = LineFollowingPolicy(
        position_estimator,
        pid_controller,
        pid_circular,
        config.LEFT_BASE_VOLTAGE,
        config.RIGHT_BASE_VOLTAGE,
        config.MOTOR_START_VOLTAGE,
        config.MAX_MOTOR_VOLTAGE,
        config.STOP_WHEN_LINE_LOST,
        config.LOST_TURN_VOLTAGE,
        config.ENABLE_INTERSECTION_STRATEGY,
        config.INTERSECTION_BLACK_COUNT,
        config.LEFT_INTERSECTION_BASE_VOLTAGE,
        config.RIGHT_INTERSECTION_BASE_VOLTAGE,
        config.INTERSECTION_DIFFERENTIAL_VOLTAGE,
        config.INTERSECTION_TURN_DIRECTION,
        config.ENABLE_CORNER_STRATEGY,
        config.CORNER_TURN_VOLTAGE,
        config.CORNER_PIVOT_ENABLED,
        config.ENABLE_CIRCULAR_CURVE_STRATEGY,
        config.CIRCULAR_CURVE_EXIT_COUNT,
        config.CIRCULAR_CURVE_EXIT_BLACK_COUNT,
        config.CIRCULAR_CURVE_ENTER_COUNT,
        config.ENABLE_CAMERA_FEEDFORWARD,
        config.CAMERA_MIN_QUALITY,
        config.CAMERA_STRAIGHT_CURVE_THRESHOLD,
        config.CAMERA_STRAIGHT_SPEED_GAIN,
        config.CAMERA_CURVE_SLOWDOWN_GAIN,
        config.CAMERA_TURN_FF_GAIN,
        config.CAMERA_MAX_SPEED_SCALE,
        config.CAMERA_MIN_SPEED_SCALE,
        config.POSITION_FILTER_ALPHA,
        config.ENABLE_POSITION_FILTER,
        config.STRAIGHT_POSITION_DEADBAND,
        config.STRAIGHT_POSITION_DEADBAND_CIRCULAR,
        config.STRAIGHT_CORRECTION_DEADBAND,
        config.TURN_STRATEGY_THRESHOLD,
        config.VOLTAGE_FILTER_ALPHA,
        config.BRAKE_MAX_VOLTAGE,
    )
    attitude_link = AttitudeLink(
        config.UART_RX_PIN,
        config.UART_TX_PIN,
        config.UART_BAUDRATE,
        config.UART_TIMEOUT_MS,
        config.UART_DEBUG_PRINT,
    )

    ble_debug = BLEDebug(
        name=config.BLE_DEVICE_NAME,
        enabled=config.BLE_DEBUG_ENABLED,
    )

    return LineTrackingApp(
        sensors,
        drive,
        policy,
        config.CONTROL_PERIOD_MS,
        attitude_link,
        config.DEBUG_PRINT,
        ble_debug,
    )


def main():
    """烧录入口函数。"""
    print("main.py started.")

    wifi_connect(
        config.WIFI_SSID, config.WIFI_PASSWORD,
        hostname=config.WIFI_HOSTNAME,
        static_ip=config.WIFI_STATIC_IP,
        static_mask=config.WIFI_STATIC_MASK,
        static_gw=config.WIFI_STATIC_GW,
        static_dns=config.WIFI_STATIC_DNS,
    )
    start_webrepl(config.WEBREPL_PASSWORD)

    try:
        app = build_app()
        app.run()
    except Exception as error:
        print("ERROR: {}".format(error))
        raise


if __name__ == "__main__":
    main()
