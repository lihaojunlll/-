from machine import Pin, PWM


class DCMotor:
    """占空比直接控制直流电机。"""

    def __init__(self, in1_pin, in2_pin, pwm_freq,
                 min_duty, max_duty, polarity=1,
                 reverse_low=False):
        self.min_duty = min_duty
        self.max_duty = max_duty
        self.polarity = 1 if polarity >= 0 else -1
        self.reverse_low = reverse_low
        self.pwm_forward = PWM(Pin(in1_pin, Pin.OUT), freq=pwm_freq, duty=0)
        self.pwm_reverse = PWM(Pin(in2_pin, Pin.OUT), freq=pwm_freq, duty=0)

    def _clamp(self, duty):
        if duty == 0:
            return 0
        sign = 1 if duty > 0 else -1
        value = abs(duty)
        if value < self.min_duty:
            if self.reverse_low:
                t = value / self.min_duty
                value = self.max_duty * (1 - t) + self.min_duty * t
                sign = -sign
            else:
                value = self.min_duty
        if value > self.max_duty:
            value = self.max_duty
        return sign * int(value)

    def set_duty(self, duty):
        duty = self._clamp(duty * self.polarity)
        if duty > 0:
            self.pwm_forward.duty(duty)
            self.pwm_reverse.duty(0)
        elif duty < 0:
            self.pwm_forward.duty(0)
            self.pwm_reverse.duty(-duty)
        else:
            self.pwm_forward.duty(0)
            self.pwm_reverse.duty(0)

    def stop(self):
        self.set_duty(0)

    def close(self):
        self.stop()
        self.pwm_forward.deinit()
        self.pwm_reverse.deinit()


class DifferentialDrive:
    """双电机差速底盘接口。"""

    def __init__(self, left_motor, right_motor):
        self.left_motor = left_motor
        self.right_motor = right_motor

    def set_duty(self, left_duty, right_duty):
        self.left_motor.set_duty(left_duty)
        self.right_motor.set_duty(right_duty)

    def stop(self):
        self.left_motor.stop()
        self.right_motor.stop()

    def close(self):
        self.left_motor.close()
        self.right_motor.close()
