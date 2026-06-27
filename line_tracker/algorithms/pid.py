class PIDController:
    """简单 PID 控制器，用于把巡线误差转换为差速电压。"""

    def __init__(self, kp, ki, kd, output_limit):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = abs(output_limit)
        self.integral = 0.0
        self.last_error = 0.0
        self.p_term = 0.0
        self.i_term = 0.0
        self.d_term = 0.0

    def reset(self):
        self.integral = 0.0
        self.last_error = 0.0

    def update(self, error, dt):
        if dt <= 0:
            dt = 0.001

        self.integral += error * dt
        derivative = (error - self.last_error) / dt
        self.last_error = error

        self.p_term = self.kp * error
        self.i_term = self.ki * self.integral
        self.d_term = self.kd * derivative

        output = self.p_term + self.i_term + self.d_term

        if output > self.output_limit:
            output = self.output_limit
        elif output < -self.output_limit:
            output = -self.output_limit

        return output
