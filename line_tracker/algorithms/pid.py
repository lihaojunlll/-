class PIDController:
    """简单 PID 控制器，用于把巡线误差转换为差速电压。"""

    def __init__(self, kp, ki, kd, output_limit):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = abs(output_limit)
        self.integral = 0.0
        self.last_error = 0.0

    def reset(self):
        self.integral = 0.0
        self.last_error = 0.0

    def update(self, error, dt):
        if dt <= 0:
            dt = 0.001

        self.integral += error * dt
        derivative = (error - self.last_error) / dt
        self.last_error = error

        output = (
            self.kp * error
            + self.ki * self.integral
            + self.kd * derivative
        )

        if output > self.output_limit:
            output = self.output_limit
        elif output < -self.output_limit:
            output = -self.output_limit

        return output
