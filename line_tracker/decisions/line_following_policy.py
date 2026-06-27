class LineFollowingPolicy:
    """Convert line position and feedforward hints into motor voltages."""

    def __init__(self, position_estimator, pid_controller, pid_circular,
                 left_base_voltage,
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
                 corner_pivot_enabled=True,
                  enable_circular_curve_strategy=False,
                  circular_curve_exit_count=10,
                 circular_curve_exit_black_count=3,
                 circular_curve_enter_count=5,
                 enable_camera_feedforward=False,
                 camera_min_quality=0.55,
                 camera_straight_curve_threshold=0.18,
                 camera_straight_speed_gain=0.12,
                 camera_curve_slowdown_gain=0.28,
                 camera_turn_ff_gain=0.55,
                 camera_max_speed_scale=1.10,
                 camera_min_speed_scale=0.72,
                  position_filter_alpha=0.55,
                  enable_position_filter=True,
                  straight_position_deadband=0.35,
                  straight_deadband_circular=0.60,
                  straight_correction_deadband=0.12,
                  turn_strategy_threshold=0.18,
                  voltage_filter_alpha=0.60):
        self.position_estimator = position_estimator
        self.pid_controller = pid_controller
        self.pid_circular = pid_circular
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
        self.enable_circular_curve_strategy = enable_circular_curve_strategy
        self.circular_curve_exit_count = circular_curve_exit_count
        self.circular_curve_exit_black_count = circular_curve_exit_black_count
        self.circular_curve_enter_count = circular_curve_enter_count
        self.in_circular_curve = False
        self._circular_counter = 0
        self._exit_cooldown = self.circular_curve_enter_count
        self.enable_camera_feedforward = enable_camera_feedforward
        self.camera_min_quality = camera_min_quality
        self.camera_straight_curve_threshold = camera_straight_curve_threshold
        self.camera_straight_speed_gain = camera_straight_speed_gain
        self.camera_curve_slowdown_gain = camera_curve_slowdown_gain
        self.camera_turn_ff_gain = camera_turn_ff_gain
        self.camera_max_speed_scale = camera_max_speed_scale
        self.camera_min_speed_scale = camera_min_speed_scale
        self.position_filter_alpha = position_filter_alpha
        self.enable_position_filter = enable_position_filter
        self.straight_position_deadband = straight_position_deadband
        self.straight_deadband_circular = straight_deadband_circular
        self.straight_correction_deadband = straight_correction_deadband
        self.turn_strategy_threshold = turn_strategy_threshold
        self.voltage_filter_alpha = voltage_filter_alpha
        self.filtered_left = 0.0
        self.filtered_right = 0.0
        self.last_turn_sign = 1
        self.last_seen_side = 1
        self.last_black_flags = [0, 0, 1, 0, 0]
        self.last_seen_position = 0.0
        self.filtered_position = 0.0

    def _limit_output_voltage(self, voltage):
        if voltage == 0:
            return 0

        sign = 1 if voltage > 0 else -1
        value = abs(voltage)
        if value < self.start_voltage:
            value = self.start_voltage
        if value > self.max_voltage:
            value = self.max_voltage
        return sign * value

    def _build_decision(self, left_voltage, right_voltage, position, line_found,
                        correction, strategy, black_count, search_side=None):
        if search_side is None:
            search_side = self.last_seen_side
        return {
            "left_voltage": self._limit_output_voltage(left_voltage),
            "right_voltage": self._limit_output_voltage(right_voltage),
            "position": position,
            "line_found": line_found,
            "correction": correction,
            "strategy": strategy,
            "black_count": black_count,
            "last_seen_side": self.last_seen_side,
            "last_black_flags": self.last_black_flags,
            "last_seen_position": self.last_seen_position,
            "search_side": search_side,
            "speed_scale": 1.0,
            "turn_ff": 0.0,
            "cam_state": "NO_CAM",
             "in_circular_curve": self.in_circular_curve,
            "circ_counter": self._circular_counter,
            "error": self.filtered_position,
        }

    def _intersection_turn_sign(self):
        if self.intersection_turn_direction == "left":
            return -1
        if self.intersection_turn_direction == "right":
            return 1
        if self.intersection_turn_direction == "last":
            return self.last_turn_sign
        return 0

    def _is_sharp_left_corner(self, black_flags):
        return black_flags in (
            [1, 1, 0, 0, 0],
            [1, 1, 1, 0, 0],
        )

    def _is_sharp_right_corner(self, black_flags):
        return black_flags in (
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

        self.last_turn_sign = turn_sign
        strategy = "SHARP_RIGHT" if turn_sign > 0 else "SHARP_LEFT"
        return self._build_decision(
            left_voltage, right_voltage, position, line_found,
            voltage * turn_sign, strategy, black_count
        )

    def _camera_feedforward(self, attitude):
        if not self.enable_camera_feedforward or not attitude:
            return 1.0, 0.0, "NO_CAM"
        if not attitude.get("cam_fresh", False):
            return 1.0, 0.0, "CAM_OLD"

        quality = attitude.get("cam_quality", 0.0)
        if quality < self.camera_min_quality:
            return 1.0, 0.0, "CAM_LOWQ"

        curve = attitude.get("cam_curve", 0.0)
        far = attitude.get("cam_far", 0.0)
        abs_curve = abs(curve)

        speed_scale = 1.0 - self.camera_curve_slowdown_gain * abs_curve
        if abs_curve <= self.camera_straight_curve_threshold:
            speed_scale += self.camera_straight_speed_gain
        speed_scale = max(
            self.camera_min_speed_scale,
            min(self.camera_max_speed_scale, speed_scale),
        )

        turn_ff = self.camera_turn_ff_gain * (0.75 * curve + 0.25 * far)
        if curve > self.camera_straight_curve_threshold:
            cam_state = "CAM_RIGHT"
        elif curve < -self.camera_straight_curve_threshold:
            cam_state = "CAM_LEFT"
        else:
            cam_state = "CAM_STRAIGHT"
        return speed_scale, turn_ff, cam_state

    def _control_position(self, position):
        if self.enable_position_filter:
            alpha = self.position_filter_alpha
            self.filtered_position = (
                alpha * self.filtered_position + (1.0 - alpha) * position
            )
        else:
            self.filtered_position = position

        deadband = (self.straight_deadband_circular if self.in_circular_curve
                    else self.straight_position_deadband)
        if abs(self.filtered_position) <= deadband:
            return 0.0
        return self.filtered_position

    def _remember_seen_side(self, black_flags, position):
        if not black_flags or sum(black_flags) == 0:
            return
        self.last_black_flags = list(black_flags)
        self.last_seen_position = position

        weighted_sum = 0
        for flag, weight in zip(black_flags, self.position_estimator.weights):
            weighted_sum += flag * weight

        if weighted_sum < 0:
            self.last_seen_side = -1
            self.last_turn_sign = -1
        elif weighted_sum > 0:
            self.last_seen_side = 1
            self.last_turn_sign = 1

    def _is_all_black(self, black_flags):
        return black_flags == [1, 1, 1, 1, 1]

    def decide(self, black_flags, dt, attitude=None):
        black_count = sum(black_flags)
        position, line_found = self.position_estimator.estimate(black_flags)
        control_position = self._control_position(position)

        if self.enable_circular_curve_strategy:
            if self.in_circular_curve:
                self._circular_counter += 1
                if self._is_all_black(black_flags):
                    if self._circular_counter >= self.circular_curve_exit_count:
                        self.in_circular_curve = False
                        self._circular_counter = 0
                        self._exit_cooldown = 0
                elif black_count >= self.circular_curve_exit_black_count:
                    if self._circular_counter >= self.circular_curve_exit_count:
                        self.in_circular_curve = False
                        self._circular_counter = 0
                        self._exit_cooldown = 0
            else:
                self._exit_cooldown += 1
                if self._is_all_black(black_flags) and self._exit_cooldown >= self.circular_curve_enter_count:
                    self.in_circular_curve = True
                    self._circular_counter = 0
                    self.pid_circular.reset()

        if line_found:
            self._remember_seen_side(black_flags, position)

        if self.enable_corner_strategy:
            if self._is_sharp_left_corner(black_flags) and self.last_seen_side < 0:
                return self._build_corner_decision(
                    -1, position, line_found, black_count
                )
            if self._is_sharp_right_corner(black_flags) and self.last_seen_side > 0:
                return self._build_corner_decision(
                    1, position, line_found, black_count
                )

        if not line_found:
            self.pid_controller.reset()
            if self.stop_when_lost:
                return self._build_decision(
                    0, 0, position, line_found, 0, "LOST_STOP", black_count
                )

            if self.last_seen_side < 0:
                self.last_turn_sign = -1
                return self._build_decision(
                    -self.search_voltage, self.search_voltage,
                    position, line_found, 0, "LOST_SEARCH_LEFT", black_count,
                    -1
                )
            self.last_turn_sign = 1
            return self._build_decision(
                self.search_voltage, -self.search_voltage,
                position, line_found, 0, "LOST_SEARCH_RIGHT", black_count,
                1
            )

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
                position, line_found, correction, strategy, black_count
            )

        speed_scale, turn_ff, cam_state = self._camera_feedforward(attitude)

        pid = self.pid_circular if self.in_circular_curve else self.pid_controller
        correction = pid.update(control_position, dt) + turn_ff
        if abs(correction) <= self.straight_correction_deadband:
            correction = 0.0

        left_voltage = self.left_base_voltage * speed_scale
        right_voltage = self.right_base_voltage * speed_scale
        if correction > 0:
            left_voltage += correction
        else:
            right_voltage -= correction

        alpha = self.voltage_filter_alpha
        self.filtered_left = alpha * self.filtered_left + (1 - alpha) * left_voltage
        self.filtered_right = alpha * self.filtered_right + (1 - alpha) * right_voltage
        left_voltage = self.filtered_left
        right_voltage = self.filtered_right

        if correction > self.turn_strategy_threshold:
            self.last_turn_sign = 1
            strategy = "TURN_RIGHT"
        elif correction < -self.turn_strategy_threshold:
            self.last_turn_sign = -1
            strategy = "TURN_LEFT"
        else:
            strategy = "GO_STRAIGHT"

        if cam_state not in ("NO_CAM", "CAM_OLD", "CAM_LOWQ"):
            strategy = "%s+%s" % (strategy, cam_state)

        decision = self._build_decision(
            left_voltage, right_voltage, position, line_found,
            correction, strategy, black_count
        )
        decision["speed_scale"] = speed_scale
        decision["turn_ff"] = turn_ff
        decision["cam_state"] = cam_state
        decision["error"] = control_position
        decision["p_term"] = pid.p_term
        decision["i_term"] = pid.i_term
        decision["d_term"] = pid.d_term
        return decision
