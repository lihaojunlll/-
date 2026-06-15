import sys
import types
import unittest


# 在电脑上模拟 MicroPython 的 machine 模块，使调度层可以被导入。
machine = types.ModuleType("machine")
machine.Pin = object
machine.PWM = object
machine.ADC = object
machine.disable_irq = lambda: 0
machine.enable_irq = lambda state: None
sys.modules.setdefault("machine", machine)

from Algorithm import PIDController
from Policy import TrackingPolicy
from car import Car


class FakeMotor:
    """记录电机指令，不访问真实 GPIO。"""

    def __init__(self):
        self.command = None

    def set_speed(self, left_speed, right_speed):
        self.command = (left_speed, right_speed)

    def stop(self):
        self.command = (0, 0)

    def deinit(self):
        pass


class FakeTraction:
    """向调度层提供固定的五路灰度数据。"""

    def __init__(self, samples):
        self.samples = samples

    def read(self):
        return self.samples


class AlgorithmTest(unittest.TestCase):
    def test_pid_output_limit(self):
        pid = PIDController(kp=100, output_limits=(-50, 50))
        self.assertEqual(pid.update(1), 50)
        self.assertEqual(pid.update(-1), -50)


class PolicyTest(unittest.TestCase):
    def test_center_line_moves_forward(self):
        command = TrackingPolicy().decide((3000, 3000, 1000, 3000, 3000))
        self.assertEqual(command.state, "tracking")
        self.assertEqual((command.left_speed, command.right_speed), (40, 40))

    def test_line_on_left_turns_left(self):
        command = TrackingPolicy().decide((1000, 3000, 3000, 3000, 3000))
        self.assertLess(command.left_speed, command.right_speed)

    def test_line_on_right_turns_right(self):
        command = TrackingPolicy().decide((3000, 3000, 3000, 3000, 1000))
        self.assertGreater(command.left_speed, command.right_speed)

    def test_no_line_at_start_stops(self):
        command = TrackingPolicy().decide((3000, 3000, 3000, 3000, 3000))
        self.assertEqual(command.state, "line_not_found")
        self.assertEqual((command.left_speed, command.right_speed), (0, 0))


class IntegrationTest(unittest.TestCase):
    def test_control_step_passes_command_to_motor(self):
        motor = FakeMotor()
        traction = FakeTraction((3000, 3000, 1000, 3000, 3000))
        car = Car(motor=motor, traction=traction, policy=TrackingPolicy())

        samples, command = car.control_step()

        self.assertEqual(samples, traction.samples)
        self.assertEqual(motor.command, (40, 40))
        self.assertEqual(command.state, "tracking")


if __name__ == "__main__":
    unittest.main()
