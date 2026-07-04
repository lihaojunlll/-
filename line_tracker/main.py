import config
from algorithms.line_position import LinePositionEstimator
from algorithms.pid import PIDController
from applications.line_tracking_app import LineTrackingApp
from decisions.line_following_policy import LineFollowingPolicy
from interfaces.gray_sensor import GraySensorArray
from interfaces.motor_driver import DCMotor, DifferentialDrive


def build_app():
    sensors = GraySensorArray(
        pins=config.GRAY_SENSOR_PINS,
        thresholds=config.GRAY_THRESHOLDS,
        black_when_below=config.BLACK_WHEN_RAW_BELOW_THRESHOLD,
        enabled_mask=config.GRAY_SENSOR_ENABLED,
    )

    left_motor = DCMotor(
        config.LEFT_MOTOR_IN1,
        config.LEFT_MOTOR_IN2,
        config.PWM_FREQ,
        config.MIN_DUTY,
        config.MAX_DUTY,
        config.LEFT_MOTOR_POLARITY,
        config.REVERSE_ON_LOW_DUTY,
    )
    right_motor = DCMotor(
        config.RIGHT_MOTOR_IN1,
        config.RIGHT_MOTOR_IN2,
        config.PWM_FREQ,
        config.MIN_DUTY,
        config.MAX_DUTY,
        config.RIGHT_MOTOR_POLARITY,
        config.REVERSE_ON_LOW_DUTY,
    )
    drive = DifferentialDrive(left_motor, right_motor)

    position_estimator = LinePositionEstimator(config.SENSOR_WEIGHTS)
    pid_controller = PIDController(
        config.KP,
        config.KI,
        config.KD,
        config.MAX_DUTY,
    )
    policy = LineFollowingPolicy(
        position_estimator,
        pid_controller,
        config.LEFT_BASE_DUTY,
        config.RIGHT_BASE_DUTY,
        config.MIN_DUTY,
        config.MAX_DUTY,
        config.MOTOR_MODE,
        config.STOP_WHEN_LOST,
        config.LOST_TURN_DUTY,
        config.REVERSE_ON_LOW_DUTY,
    )

    return LineTrackingApp(
        sensors,
        drive,
        policy,
        config.CONTROL_PERIOD_MS,
        config.DEBUG_PRINT,
    )


def main():
    print("main.py started.")

    try:
        app = build_app()
        app.run()
    except Exception as error:
        print("ERROR: {}".format(error))
        raise


if __name__ == "__main__":
    main()
