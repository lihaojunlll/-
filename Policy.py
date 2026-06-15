from Algorithm import PIDController
from Config import AlgorithmConfig, PolicyConfig


class DriveCommand:
    """策略层传递给电机驱动层的行驶指令。"""

    def __init__(self, left_speed, right_speed, state, line, error=None):
        self.left_speed = int(left_speed)
        self.right_speed = int(right_speed)
        self.state = state
        self.line = tuple(line)
        self.error = error

    def __repr__(self):
        return (
            "DriveCommand(left={}, right={}, state={}, line={}, error={})".format(
                self.left_speed,
                self.right_speed,
                self.state,
                self.line,
                self.error,
            )
        )

    def format_debug(self):
        """使用纯 ASCII 字符格式化调试信息。"""
        error_text = "None" if self.error is None else "{:.2f}".format(self.error)
        return (
            "state={} | line={} | error={} | left={}% | right={}%"
        ).format(
            self.state,
            self.line,
            error_text,
            self.left_speed,
            self.right_speed,
        )


class TrackingPolicy:
    """将五路灰度采样值转换为差速轮控制指令。"""

    # 权重从左到右递增，计算结果为负表示黑线偏左，为正表示黑线偏右。
    SENSOR_WEIGHTS = (-2, -1, 0, 1, 2)

    def __init__(
        self,
        thresholds=PolicyConfig.THRESHOLDS,
        black_is_high=PolicyConfig.BLACK_IS_HIGH,
        base_speed=PolicyConfig.BASE_SPEED,
        max_speed=PolicyConfig.MAX_SPEED,
        search_speed=PolicyConfig.SEARCH_SPEED,
        intersection_speed=PolicyConfig.INTERSECTION_SPEED,
        controller=None,
    ):
        if len(thresholds) != 5:
            raise ValueError("TrackingPolicy requires five thresholds")

        self.thresholds = tuple(thresholds)
        self.black_is_high = black_is_high
        self.base_speed = int(base_speed)
        self.max_speed = int(max_speed)
        self.search_speed = int(search_speed)
        self.intersection_speed = int(intersection_speed)

        # 允许外部注入控制器，便于更换算法或进行脱离硬件的测试。
        self.controller = (
            controller
            if controller is not None
            else PIDController(
                kp=AlgorithmConfig.TRACKING_KP,
                ki=AlgorithmConfig.TRACKING_KI,
                kd=AlgorithmConfig.TRACKING_KD,
                output_limits=AlgorithmConfig.PID_OUTPUT_LIMITS,
                integral_limits=AlgorithmConfig.PID_INTEGRAL_LIMITS,
            )
        )

        self._last_error = 0
        self._has_seen_line = False

    def classify(self, samples):
        """将五路 ADC 采样值转换为黑线检测标志，1 表示检测到黑线。"""
        if len(samples) != 5:
            raise ValueError("TrackingPolicy requires five sensor samples")

        if self.black_is_high:
            return tuple(
                1 if value >= threshold else 0
                for value, threshold in zip(samples, self.thresholds)
            )

        return tuple(
            1 if value <= threshold else 0
            for value, threshold in zip(samples, self.thresholds)
        )

    def line_error(self, line):
        """计算黑线位置误差，范围为左侧 -2.0 到右侧 2.0。"""
        detected_count = sum(line)
        if detected_count == 0:
            return None

        weighted_sum = sum(
            detected * weight
            for detected, weight in zip(line, self.SENSOR_WEIGHTS)
        )
        return weighted_sum / detected_count

    def decide(self, samples):
        """根据一次灰度采样生成左右轮控制指令。"""
        line = self.classify(samples)
        detected_count = sum(line)

        if detected_count == 0:
            return self._lost_line_command(line)

        error = self.line_error(line)
        self._has_seen_line = True

        if detected_count == 5:
            # 五路同时检测到黑线时，暂按路口处理并低速直行。
            self._last_error = error
            self.controller.reset()
            return DriveCommand(
                self.intersection_speed,
                self.intersection_speed,
                "intersection",
                line,
                error,
            )

        correction = self.controller.update(error)
        self._last_error = error

        # 误差为正表示黑线偏右，因此提高左轮速度、降低右轮速度。
        left_speed = self._limit(self.base_speed + correction)
        right_speed = self._limit(self.base_speed - correction)
        return DriveCommand(left_speed, right_speed, "tracking", line, error)

    def _lost_line_command(self, line):
        """根据最后一次看到黑线的位置生成丢线搜索指令。"""
        # 丢线后重置 PID，避免恢复循迹时产生过大的微分输出。
        self.controller.reset()

        if not self._has_seen_line:
            # 启动后从未看到黑线时保持停止，避免车辆盲目运动。
            return DriveCommand(0, 0, "line_not_found", line)

        if self._last_error < 0:
            return DriveCommand(
                -self.search_speed,
                self.search_speed,
                "search_left",
                line,
                self._last_error,
            )

        if self._last_error > 0:
            return DriveCommand(
                self.search_speed,
                -self.search_speed,
                "search_right",
                line,
                self._last_error,
            )

        return DriveCommand(
            self.search_speed,
            self.search_speed,
            "search_forward",
            line,
            self._last_error,
        )

    def _limit(self, speed):
        """限制策略层输出的最大轮速。"""
        return max(-self.max_speed, min(self.max_speed, int(speed)))

    def reset(self):
        """重置循迹历史状态和 PID 状态。"""
        self._last_error = 0
        self._has_seen_line = False
        self.controller.reset()
