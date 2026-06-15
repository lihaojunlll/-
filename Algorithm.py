class PIDController:
    """算法层通用的离散 PID 控制器。"""

    def __init__(
        self,
        kp,
        ki=0.0,
        kd=0.0,
        output_limits=(None, None),
        integral_limits=(None, None),
    ):
        self.kp = float(kp)
        self.ki = float(ki)
        self.kd = float(kd)
        self.output_limits = output_limits
        self.integral_limits = integral_limits

        self._integral = 0.0
        self._last_error = None

    @staticmethod
    def _clamp(value, limits):
        """将数值限制在指定范围内，None 表示该方向不限制。"""
        lower, upper = limits

        if lower is not None and value < lower:
            return lower
        if upper is not None and value > upper:
            return upper
        return value

    def update(self, error, dt=1.0):
        """
        根据本次误差计算 PID 输出。

        dt 表示两次计算之间的时间。当 PID 参数按控制周期整定时，
        保持默认值 1.0 即可。
        """
        if dt <= 0:
            raise ValueError("PID dt must be greater than zero")

        error = float(error)

        # 对积分项进行限幅，防止长时间存在误差时发生积分饱和。
        self._integral += error * dt
        self._integral = self._clamp(
            self._integral,
            self.integral_limits,
        )

        if self._last_error is None:
            # 第一次计算没有历史误差，不使用微分项。
            derivative = 0.0
        else:
            derivative = (error - self._last_error) / dt

        output = (
            self.kp * error
            + self.ki * self._integral
            + self.kd * derivative
        )
        self._last_error = error
        return self._clamp(output, self.output_limits)

    def reset(self):
        """清除积分和历史误差，供状态切换时重新开始计算。"""
        self._integral = 0.0
        self._last_error = None

    def set_gains(self, kp=None, ki=None, kd=None):
        """在运行过程中更新 PID 参数。"""
        if kp is not None:
            self.kp = float(kp)
        if ki is not None:
            self.ki = float(ki)
        if kd is not None:
            self.kd = float(kd)
