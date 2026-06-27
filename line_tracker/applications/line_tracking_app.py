import time


class LineTrackingApp:
    """正式寻迹应用主循环。"""

    def __init__(self, sensors, drive, policy, control_period_ms,
                 attitude_link, debug_print=True, debug_print_every=1):
        self.sensors = sensors
        self.drive = drive
        self.policy = policy
        self.control_period_ms = control_period_ms
        self.debug_print = debug_print
        self.attitude_link = attitude_link
        self.debug_counter = 0
        self.debug_print_every = max(1, debug_print_every)

    def run(self):
        print("Line tracking app started.")
        last_time = time.ticks_ms()

        try:
            while True:
                now = time.ticks_ms()
                dt = time.ticks_diff(now, last_time) / 1000.0
                last_time = now

                if self.attitude_link:
                    self.attitude_link.update()

                raw_values, black_flags = self.sensors.read()
                attitude = None
                if self.attitude_link:
                    attitude = self.attitude_link.snapshot()
                decision = self.policy.decide(black_flags, dt, attitude)
                left_voltage = decision["left_voltage"]
                right_voltage = decision["right_voltage"]
                self.drive.set_voltage(left_voltage, right_voltage)

                self.debug_counter += 1
                if (self.debug_print and
                        self.debug_counter % self.debug_print_every == 0):
                    imu_text = "imu=none"
                    last_side = "L" if decision.get("last_seen_side", 0) < 0 else "R"
                    search_side = "L" if decision.get("search_side", 0) < 0 else "R"
                    last_flags = decision.get("last_black_flags", [])
                    if attitude:
                        imu_text = (
                            "imu=%d,%d,%.1f,%.1f,%.1f "
                            "cam=%d,%d,%.2f,%.2f,%.2f,%.2f "
                            "lost=%d,%d,bad=%d"
                        ) % (
                            1 if attitude["fresh"] else 0,
                            attitude["seq"],
                            attitude["pitch"],
                            attitude["roll"],
                            attitude["yaw"],
                            1 if attitude["cam_fresh"] else 0,
                            attitude["cam_seq"],
                            attitude["cam_near"],
                            attitude["cam_far"],
                            attitude["cam_curve"],
                            attitude["cam_quality"],
                            attitude["lost_packets"],
                            attitude["cam_lost_packets"],
                            attitude["bad_packets"],
                        )
                    print(
                        "raw={} black={} count={} pos={:.2f} found={} "
                        "strategy={} last={} search={} last_flags={} last_pos={:.2f} "
                        "diff={:.2f}V ff={:.2f} scale={:.2f} circ={}/{} "
                        "left={:.2f}V right={:.2f}V "
                        "{}".format(
                            raw_values,
                            black_flags,
                            decision["black_count"],
                            decision["position"],
                            1 if decision["line_found"] else 0,
                            decision["strategy"],
                            last_side,
                            search_side,
                            last_flags,
                            decision.get("last_seen_position", 0.0),
                            decision["correction"],
                            decision.get("turn_ff", 0.0),
                            decision.get("speed_scale", 1.0),
                            int(decision.get("in_circular_curve", False)),
                            decision.get("circ_counter", 0),
                            left_voltage,
                            right_voltage,
                            imu_text,
                        )
                    )

                time.sleep_ms(self.control_period_ms)
        except KeyboardInterrupt:
            print("Line tracking stopped.")
        finally:
            self.drive.stop()
            self.drive.close()
            print("Motors stopped.")
