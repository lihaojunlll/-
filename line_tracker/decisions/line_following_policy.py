class LineFollowingPolicy:
    """巡线决策：把灰度位置误差转换成左右电机电压。"""

    def __init__(self, position_estimator, pid_controller, left_base_voltage,
                 right_base_voltage, start_voltage, max_voltage,
                 stop_when_lost=True, search_voltage=4.3,
                 enable_intersection_strategy=False,
                 intersection_black_count=4,
                 left_intersection_base_voltage=4.8,
                 right_intersection_base_voltage=4.8,
                 intersection_differential_voltage=1.5,
                 intersection_turn_direction="right",
                 enable_corner_strategy=False,
                 corner_turn_voltage=4.8,
                 corner_pivot_enabled=True):
        self.position_estimator = position_estimator
        self.pid_controller = pid_controller
        self.left_base_voltage = left_base_voltage
        self.right_base_voltage = right_base_voltage
        self.start_voltage = start_voltage
        self.max_voltage = max_voltage
        self.stop_when_lost = stop_when_lost
        self.search_voltage = search_voltage
        self.enable_intersection_strategy = enable_intersection_strategy
        self.intersection_black_count = intersection_black_count
        self.left_intersection_base_voltage = left_intersection_base_voltage
        self.right_intersection_base_voltage = right_intersection_base_voltage
        self.intersection_differential_voltage = intersection_differential_voltage
        self.intersection_turn_direction = intersection_turn_direction
        self.enable_corner_strategy = enable_corner_strategy
        self.corner_turn_voltage = corner_turn_voltage
        self.corner_pivot_enabled = corner_pivot_enabled
        self.last_turn_sign = 1

    def _limit_running_voltage(self, voltage):
        if voltage <= 0:
            return 0
        if voltage < self.start_voltage:
            return self.start_voltage
        if voltage > self.max_voltage:
            return self.max_voltage
        return voltage

    def _build_decision(self, left_voltage, right_voltage, position, line_found,
                        correction, strategy, black_count):
        return {
            "left_voltage": self._limit_running_voltage(left_voltage),
            "right_voltage": self._limit_running_voltage(right_voltage),
            "position": position,
            "line_found": line_found,
            "correction": correction,
            "strategy": strategy,
            "black_count": black_count,
        }

    def _intersection_turn_sign(self):
        direction = self.intersection_turn_direction
        if direction == "left":
            return -1
        if direction == "right":
            return 1
        if direction == "last":
            return self.last_turn_sign
        return 0

    def _is_sharp_left_corner(self, black_flags):
        return black_flags in (
            [1, 0, 0, 0, 0],
            [1, 1, 0, 0, 0],
            [1, 1, 1, 0, 0],
        )

    def _is_sharp_right_corner(self, black_flags):
        return black_flags in (
            [0, 0, 0, 0, 1],
            [0, 0, 0, 1, 1],
            [0, 0, 1, 1, 1],
        )

    def _build_corner_decision(self, turn_sign, position, line_found, black_count):
        voltage = self.corner_turn_voltage
        if self.corner_pivot_enabled:
            left_voltage = voltage * turn_sign
            right_voltage = -voltage * turn_sign
        else:
            left_voltage = self.left_base_voltage + voltage * turn_sign
            right_voltage = self.right_base_voltage - voltage * turn_sign

        if turn_sign > 0:
            strategy = "SHARP_RIGHT"
        else:
            strategy = "SHARP_LEFT"

        self.last_turn_sign = turn_sign
        return {
            "left_voltage": left_voltage,
            "right_voltage": right_voltage,
            "position": position,
            "line_found": line_found,
            "correction": voltage * turn_sign,
            "strategy": strategy,
            "black_count": black_count,
        }

    def decide(self, black_flags, dt):
        black_count = sum(black_flags)
        position, line_found = self.position_estimator.estimate(black_flags)

        if self.enable_corner_strategy:
            if self._is_sharp_left_corner(black_flags):
                return self._build_corner_decision(
                    -1, position, line_found, black_count
                )
            if self._is_sharp_right_corner(black_flags):
                return self._build_corner_decision(
                    1, position, line_found, black_count
                )

        if not line_found:
            self.pid_controller.reset()
            if self.stop_when_lost:
                return self._build_decision(
                    0, 0, position, line_found, 0, "LOST_STOP", black_count
                )

            if position < 0:
                self.last_turn_sign = -1
                return {
                    "left_voltage": -self.search_voltage,
                    "right_voltage": self.search_voltage,
                    "position": position,
                    "line_found": line_found,
                    "correction": 0,
                    "strategy": "LOST_SEARCH_LEFT",
                    "black_count": black_count,
                }
            self.last_turn_sign = 1
            return {
                "left_voltage": self.search_voltage,
                "right_voltage": -self.search_voltage,
                "position": position,
                "line_found": line_found,
                "correction": 0,
                "strategy": "LOST_SEARCH_RIGHT",
                "black_count": black_count,
            }

        # 大面积黑线时，位置平均值可能接近 0，普通 PID 会误判成直行。
        if (self.enable_intersection_strategy and
                black_count >= self.intersection_black_count):
            turn_sign = self._intersection_turn_sign()
            correction = turn_sign * self.intersection_differential_voltage
            if turn_sign > 0:
                strategy = "INTERSECTION_RIGHT"
            elif turn_sign < 0:
                strategy = "INTERSECTION_LEFT"
            else:
                strategy = "INTERSECTION_STRAIGHT"
            return self._build_decision(
                self.left_intersection_base_voltage + correction,
                self.right_intersection_base_voltage - correction,
                position,
                line_found,
                correction,
                strategy,
                black_count,
            )

        # 误差为正表示黑线偏右，小车需要右转：左轮更快、右轮更慢。
        correction = self.pid_controller.update(position, dt)
        left_voltage = self.left_base_voltage + correction
        right_voltage = self.right_base_voltage - correction

        if correction > 0.05:
            self.last_turn_sign = 1
            strategy = "TURN_RIGHT"
        elif correction < -0.05:
            self.last_turn_sign = -1
            strategy = "TURN_LEFT"
        else:
            strategy = "GO_STRAIGHT"

        return self._build_decision(
            left_voltage,
            right_voltage,
            position,
            line_found,
            correction,
            strategy,
            black_count,
        )
