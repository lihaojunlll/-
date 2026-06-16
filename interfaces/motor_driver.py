from machine import Pin, PWM


class VoltageMotor:
    """用等效电压控制单个直流电机。"""

    def __init__(self, in1_pin, in2_pin, pwm_freq, supply_voltage,
                 start_voltage, max_voltage, polarity=1):
        self.supply_voltage = supply_voltage
        self.start_voltage = start_voltage
        self.max_voltage = max_voltage
        self.polarity = 1 if polarity >= 0 else -1
        self.pwm_forward = PWM(Pin(in1_pin, Pin.OUT), freq=pwm_freq, duty=0)
        self.pwm_reverse = PWM(Pin(in2_pin, Pin.OUT), freq=pwm_freq, duty=0)

    def _limit_voltage(self, voltage):
        if voltage == 0:
            return 0

        sign = 1 if voltage > 0 else -1
        value = abs(voltage)

        # 非零输出时至少给到启动电压，避免低电压只发热不转。
        if value < self.start_voltage:
            value = self.start_voltage

        if value > self.max_voltage:
            value = self.max_voltage

        return sign * value

    def _voltage_to_duty(self, voltage):
        ratio = abs(voltage) / self.supply_voltage
        ratio = max(0.0, min(1.0, ratio))
        return int(ratio * 1023)

    def set_voltage(self, voltage):
        voltage = voltage * self.polarity
        voltage = self._limit_voltage(voltage)
        duty = self._voltage_to_duty(voltage)

        if voltage > 0:
            self.pwm_forward.duty(duty)
            self.pwm_reverse.duty(0)
        elif voltage < 0:
            self.pwm_forward.duty(0)
            self.pwm_reverse.duty(duty)
        else:
            self.pwm_forward.duty(0)
            self.pwm_reverse.duty(0)

    def stop(self):
        self.set_voltage(0)

    def close(self):
        self.stop()
        self.pwm_forward.deinit()
        self.pwm_reverse.deinit()


class DifferentialDrive:
    """双电机差速底盘接口。"""

    def __init__(self, left_motor, right_motor):
        self.left_motor = left_motor
        self.right_motor = right_motor

    def set_voltage(self, left_voltage, right_voltage):
        self.left_motor.set_voltage(left_voltage)
        self.right_motor.set_voltage(right_voltage)

    def stop(self):
        self.left_motor.stop()
        self.right_motor.stop()

    def close(self):
        self.left_motor.close()
        self.right_motor.close()
