import time


class LineTrackingApp:
    """正式寻迹应用主循环。"""

    def __init__(self, sensors, drive, policy, control_period_ms,
                 attitude_link, debug_print=True,
                 ble_debug=None):
        self.sensors = sensors
        self.drive = drive
        self.policy = policy
        self.control_period_ms = control_period_ms
        self.debug_print = debug_print
        self.attitude_link = attitude_link
        self.ble_debug = ble_debug

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

                if self.debug_print:
                    debug_line = (
                        "raw={} black={} count={} pos={:.2f} fpos={:.2f} "
                        "dt={:.3f} err={:.2f} found={} strategy={} last={} search={} "
                        "last_flags={} last_pos={:.2f} "
                        "diff={:.2f}V P={:.2f} I={:.2f} D={:.2f} "
                        "left={:.2f}V right={:.2f}V "
                        "circ={}/{}".format(
                            raw_values,
                            black_flags,
                            decision["black_count"],
                            decision["position"],
                            self.policy.filtered_position,
                            dt,
                            decision.get("error", 0.0),
                            1 if decision["line_found"] else 0,
                            decision["strategy"],
                            "L" if decision.get("last_seen_side", 0) < 0 else "R",
                            "L" if decision.get("search_side", 0) < 0 else "R",
                            decision.get("last_black_flags", []),
                            decision.get("last_seen_position", 0.0),
                            decision["correction"],
                            decision.get("p_term", 0.0),
                            decision.get("i_term", 0.0),
                            decision.get("d_term", 0.0),
                            left_voltage,
                            right_voltage,
                            int(decision.get("in_circular_curve", False)),
                            decision.get("circ_counter", 0),
                        )
                    )
                    print(debug_line)
                    if self.ble_debug:
                        self.ble_debug.send(debug_line)

                time.sleep_ms(self.control_period_ms)
        except KeyboardInterrupt:
            print("Line tracking stopped.")
        finally:
            self.drive.stop()
            self.drive.close()
            print("Motors stopped.")
