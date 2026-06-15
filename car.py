import time

from Config import AppConfig
from Motor import Motor
from Policy import TrackingPolicy
from Traction import Traction


class Car:
    """协调感知层、策略层、算法层和执行层的应用调度类。"""

    def __init__(self, motor=None, traction=None, policy=None):
        self.motor = motor if motor is not None else Motor()
        self.traction = traction if traction is not None else Traction()
        self.policy = policy if policy is not None else TrackingPolicy()

    def control_step(self):
        """执行一次完整的感知、决策和电机控制流程。"""
        samples = self.traction.read()
        command = self.policy.decide(samples)
        self.motor.set_speed(command.left_speed, command.right_speed)
        return samples, command

    @staticmethod
    def print_control_info(samples, command):
        """使用纯 ASCII 字符输出灰度数据和控制结果。"""
        print("ADC:", samples)
        print("CONTROL:", command.format_debug())
        print("-" * 50)

    def run_tracking(
        self,
        interval_ms=AppConfig.CONTROL_INTERVAL_MS,
        debug_interval_ms=AppConfig.DEBUG_INTERVAL_MS,
    ):
        """持续执行循迹控制，直到程序被中断。"""
        last_debug_time = time.ticks_ms()
        self.policy.reset()

        while True:
            samples, command = self.control_step()
            current_time = time.ticks_ms()

            if time.ticks_diff(current_time, last_debug_time) >= debug_interval_ms:
                self.print_control_info(samples, command)
                last_debug_time = current_time

            time.sleep_ms(interval_ms)

    def sensor_test(self, interval_ms=AppConfig.DEBUG_INTERVAL_MS):
        """只输出传感器和策略结果，不驱动车辆。"""
        self.motor.stop()
        while True:
            samples = self.traction.read()
            command = self.policy.decide(samples)
            self.print_control_info(samples, command)
            time.sleep_ms(interval_ms)

    def motor_test(
        self,
        speed=AppConfig.MOTOR_TEST_SPEED,
        start_delay_ms=AppConfig.MOTOR_TEST_START_DELAY_MS,
        duration_ms=AppConfig.MOTOR_TEST_DURATION_MS,
        pause_ms=AppConfig.MOTOR_TEST_PAUSE_MS,
    ):
        """分别测试两个电机，再测试整车动作。"""
        actions = (
            ("LEFT_FORWARD", lambda value: self.motor.set_speed(value, 0)),
            ("RIGHT_FORWARD", lambda value: self.motor.set_speed(0, value)),
            ("BOTH_FORWARD", lambda value: self.motor.set_speed(value, value)),
            ("BOTH_BACKWARD", lambda value: self.motor.set_speed(-value, -value)),
            ("SPIN_LEFT", lambda value: self.motor.set_speed(-value, value)),
            ("SPIN_RIGHT", lambda value: self.motor.set_speed(value, -value)),
        )

        print("Motor test started")
        print(
            "Speed={}% | expected_duty={} | duration={}ms".format(
                speed,
                abs(int(speed)) * 1023 // 100,
                duration_ms,
            )
        )
        print("Lift the wheels. Test starts in {}ms.".format(start_delay_ms))
        time.sleep_ms(start_delay_ms)

        for name, action in actions:
            before_counts = self.motor.read_encoders()
            print("Testing:", name)
            action(speed)
            time.sleep_ms(duration_ms)
            self.motor.stop()
            after_counts = self.motor.read_encoders()
            print(
                "Done={} | left_encoder_delta={} | right_encoder_delta={}".format(
                    name,
                    after_counts[0] - before_counts[0],
                    after_counts[1] - before_counts[1],
                )
            )
            time.sleep_ms(pause_ms)
        print("Motor test finished. Motors stopped.")

    def stop(self):
        self.motor.stop()

    def deinit(self):
        """释放整车使用的底层硬件资源。"""
        self.motor.deinit()


def main():
    car = Car()
    print("Car system initialized")
    print("Run mode:", AppConfig.RUN_MODE)

    try:
        if AppConfig.RUN_MODE == "tracking":
            car.run_tracking()
        elif AppConfig.RUN_MODE == "motor_test":
            car.motor_test()
        else:
            car.sensor_test()
    except KeyboardInterrupt:
        print("Program interrupted")
    finally:
        car.deinit()
        print("Motors stopped. Hardware resources released.")


if __name__ == "__main__":
    main()
