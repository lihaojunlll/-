from machine import Pin, PWM, disable_irq, enable_irq

from Config import MotorConfig


class Motor:
    """双直流电机及正交编码器的底层驱动。"""

    def __init__(
        self,
        left_in1=MotorConfig.LEFT_IN1,
        left_in2=MotorConfig.LEFT_IN2,
        right_in1=MotorConfig.RIGHT_IN1,
        right_in2=MotorConfig.RIGHT_IN2,
        left_enc_a=MotorConfig.LEFT_ENCODER_A,
        left_enc_b=MotorConfig.LEFT_ENCODER_B,
        right_enc_a=MotorConfig.RIGHT_ENCODER_A,
        right_enc_b=MotorConfig.RIGHT_ENCODER_B,
        pwm_freq=MotorConfig.PWM_FREQUENCY,
        left_direction=MotorConfig.LEFT_DIRECTION,
        right_direction=MotorConfig.RIGHT_DIRECTION,
    ):
        if left_direction not in (-1, 1) or right_direction not in (-1, 1):
            raise ValueError("Motor direction must be 1 or -1")

        self._left_count = 0
        self._right_count = 0
        self._left_direction = left_direction
        self._right_direction = right_direction

        # 每个电机使用两路 PWM，实现正转、反转和停止。
        self._left_in1 = PWM(Pin(left_in1, Pin.OUT), freq=pwm_freq, duty=0)
        self._left_in2 = PWM(Pin(left_in2, Pin.OUT), freq=pwm_freq, duty=0)
        self._right_in1 = PWM(Pin(right_in1, Pin.OUT), freq=pwm_freq, duty=0)
        self._right_in2 = PWM(Pin(right_in2, Pin.OUT), freq=pwm_freq, duty=0)

        # 编码器 A 相触发中断，B 相用于判断旋转方向。
        self._left_enc_a = Pin(left_enc_a, Pin.IN, Pin.PULL_UP)
        self._left_enc_b = Pin(left_enc_b, Pin.IN, Pin.PULL_UP)
        self._right_enc_a = Pin(right_enc_a, Pin.IN, Pin.PULL_UP)
        self._right_enc_b = Pin(right_enc_b, Pin.IN, Pin.PULL_UP)

        self._left_enc_a.irq(
            trigger=Pin.IRQ_RISING, handler=self._on_left_encoder
        )
        self._right_enc_a.irq(
            trigger=Pin.IRQ_RISING, handler=self._on_right_encoder
        )

        self.stop()

    @staticmethod
    def _limit_speed(speed):
        """将速度百分比限制在 -100 到 100。"""
        return max(-100, min(100, int(speed)))

    @staticmethod
    def _set_channel(in1, in2, speed):
        """将带方向的速度值转换为两路 PWM 占空比。"""
        speed = Motor._limit_speed(speed)
        duty = abs(speed) * 1023 // 100

        if speed > 0:
            in1.duty(duty)
            in2.duty(0)
        elif speed < 0:
            in1.duty(0)
            in2.duty(duty)
        else:
            in1.duty(0)
            in2.duty(0)

    def _on_left_encoder(self, pin):
        """左编码器 A 相上升沿中断回调。"""
        if self._left_enc_b.value():
            self._left_count += 1
        else:
            self._left_count -= 1

    def _on_right_encoder(self, pin):
        """右编码器 A 相上升沿中断回调。"""
        if self._right_enc_b.value():
            self._right_count += 1
        else:
            self._right_count -= 1

    def set_speed(self, left_speed, right_speed):
        """设置左右轮速度，取值范围为 -100 到 100。"""
        self._set_channel(
            self._left_in1,
            self._left_in2,
            left_speed * self._left_direction,
        )
        self._set_channel(
            self._right_in1,
            self._right_in2,
            right_speed * self._right_direction,
        )

    def forward(self, speed=50):
        speed = abs(self._limit_speed(speed))
        self.set_speed(speed, speed)

    def backward(self, speed=50):
        speed = abs(self._limit_speed(speed))
        self.set_speed(-speed, -speed)

    def turn_left(self, speed=50):
        speed = abs(self._limit_speed(speed))
        self.set_speed(-speed, speed)

    def turn_right(self, speed=50):
        speed = abs(self._limit_speed(speed))
        self.set_speed(speed, -speed)

    def stop(self):
        self.set_speed(0, 0)

    def read_encoders(self):
        """原子读取左右编码器累计计数。"""
        # 读取期间暂时关闭中断，避免两个计数值来自不同时间点。
        irq_state = disable_irq()
        counts = (self._left_count, self._right_count)
        enable_irq(irq_state)
        return counts

    def reset_encoders(self):
        """原子清零左右编码器累计计数。"""
        irq_state = disable_irq()
        self._left_count = 0
        self._right_count = 0
        enable_irq(irq_state)

    def deinit(self):
        """停止电机并释放 PWM 和编码器中断资源。"""
        self.stop()
        self._left_enc_a.irq(handler=None)
        self._right_enc_a.irq(handler=None)
        self._left_in1.deinit()
        self._left_in2.deinit()
        self._right_in1.deinit()
        self._right_in2.deinit()
