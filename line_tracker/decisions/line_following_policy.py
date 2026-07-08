class LineFollowingPolicy:

    def __init__(self, position_estimator, pid_controller,
                 left_base_duty, right_base_duty,
                 min_duty, max_duty, mode="both",
                 stop_when_lost=True, lost_turn_duty=500,
                 reverse_low=False, camera_min_quality=0.25,
                 camera_max_slowdown=0.35, camera_turn_ff_duty=120):
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
        self.camera_min_quality = camera_min_quality
        self.camera_max_slowdown = camera_max_slowdown
        self.camera_turn_ff_duty = camera_turn_ff_duty

    def decide(self, black_flags, dt, camera=None):
        speed_scale, turn_ff, camera_active = self._camera_assist(camera)
        left_base = self.left_base_duty * speed_scale
        right_base = self.right_base_duty * speed_scale

        if tuple(black_flags) == (1, 1, 1, 1, 1):
            return self._build_decision(
                left_base + turn_ff, right_base - turn_ff, 0, True,
                speed_scale, turn_ff, camera_active)

        position, line_found = self.position_estimator.estimate(black_flags)

        if not line_found:
            self.pid_controller.reset()
            if self.stop_when_lost:
                return self._build_decision(0, 0, position, line_found,
                                            speed_scale, 0, camera_active)
            if self.last_seen_side < 0:
                return self._build_decision(
                    -self.lost_turn_duty, self.lost_turn_duty,
                    position, line_found, speed_scale, 0, camera_active)
            return self._build_decision(
                self.lost_turn_duty, -self.lost_turn_duty,
                position, line_found, speed_scale, 0, camera_active)

        self._remember_seen_side(position)
        correction = self.pid_controller.update(position, dt)
        left_duty = left_base
        right_duty = right_base
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

        left_duty += turn_ff
        right_duty -= turn_ff
        return self._build_decision(left_duty, right_duty, position,
                                    line_found, speed_scale, turn_ff,
                                    camera_active)

    def _build_decision(self, left_duty, right_duty, position, line_found,
                        speed_scale=1.0, camera_turn_ff=0,
                        camera_active=False):
        return {
            "left_duty": self._clamp(left_duty),
            "right_duty": self._clamp(right_duty),
            "position": position,
            "line_found": line_found,
            "correction": left_duty - self.left_base_duty,
            "camera_active": camera_active,
            "camera_speed_scale": speed_scale,
            "camera_turn_ff": camera_turn_ff,
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

    def _camera_assist(self, camera):
        if not camera or not camera.get("cam_fresh", False):
            return 1.0, 0, False

        quality = camera.get("cam_quality", 0.0)
        if quality < self.camera_min_quality:
            return 1.0, 0, False

        slowdown = camera.get("cam_slowdown", abs(camera.get("cam_curve", 0.0)))
        slowdown = max(0.0, min(1.0, slowdown))
        speed_scale = 1.0 - self.camera_max_slowdown * slowdown
        if self.reverse_low:
            min_scale = max(float(self.min_duty) / self.left_base_duty,
                            float(self.min_duty) / self.right_base_duty)
            if speed_scale < min_scale:
                speed_scale = min_scale

        turn = camera.get("cam_turn", 0)
        if turn == 0:
            curve = camera.get("cam_curve", 0.0)
            if curve > 0.28:
                turn = 1
            elif curve < -0.28:
                turn = -1

        turn_ff = int(turn * self.camera_turn_ff_duty * slowdown)
        return speed_scale, turn_ff, True
