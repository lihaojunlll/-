class LineFollowingPolicy:

    def __init__(self, position_estimator, pid_controller,
                 left_base_duty, right_base_duty,
                 min_duty, max_duty, mode="both",
                 stop_when_lost=True, lost_turn_duty=500,
                 reverse_low=False):
        self.position_estimator = position_estimator
        self.pid_controller = pid_controller
        self.left_base_duty = left_base_duty
        self.right_base_duty = right_base_duty
        self.min_duty = min_duty
        self.max_duty = max_duty
        self.mode = mode
        self.stop_when_lost = stop_when_lost
        self.lost_turn_duty = lost_turn_duty
        self.last_seen_side = 1
        self.reverse_low = reverse_low

    def decide(self, black_flags, dt):
        if tuple(black_flags) == (1, 1, 1, 1, 1):
            return self._build_decision(
                self.left_base_duty, self.right_base_duty, 0, True)

        position, line_found = self.position_estimator.estimate(black_flags)

        if not line_found:
            self.pid_controller.reset()
            if self.stop_when_lost:
                return self._build_decision(0, 0, position, line_found)
            if self.last_seen_side < 0:
                return self._build_decision(
                    -self.lost_turn_duty, self.lost_turn_duty,
                    position, line_found)
            return self._build_decision(
                self.lost_turn_duty, -self.lost_turn_duty,
                position, line_found)

        self._remember_seen_side(position)
        correction = self.pid_controller.update(position, dt)
        left_duty = self.left_base_duty
        right_duty = self.right_base_duty
        if self.mode == "both":
            left_duty += correction
            right_duty -= correction
        elif self.mode == "add":
            if correction > 0:
                left_duty += correction
            else:
                right_duty -= correction
        elif self.mode == "sub":
            if correction > 0:
                right_duty -= correction
            else:
                left_duty += correction

        return self._build_decision(left_duty, right_duty, position, line_found)

    def _build_decision(self, left_duty, right_duty, position, line_found):
        return {
            "left_duty": self._clamp(left_duty),
            "right_duty": self._clamp(right_duty),
            "position": position,
            "line_found": line_found,
            "correction": left_duty - self.left_base_duty,
        }

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

    def _remember_seen_side(self, position):
        if position < 0:
            self.last_seen_side = -1
        elif position > 0:
            self.last_seen_side = 1
