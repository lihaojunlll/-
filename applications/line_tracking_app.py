import time


class LineTrackingApp:
    """正式寻迹应用主循环。"""

    def __init__(self, sensors, drive, policy, control_period_ms,
                 debug_print=True):
        self.sensors = sensors
        self.drive = drive
        self.policy = policy
        self.control_period_ms = control_period_ms
        self.debug_print = debug_print

    def run(self):
        print("Line tracking app started.")
        last_time = time.ticks_ms()

        try:
            while True:
                now = time.ticks_ms()
                dt = time.ticks_diff(now, last_time) / 1000.0
                last_time = now

                raw_values, black_flags = self.sensors.read()
                decision = self.policy.decide(black_flags, dt)
                left_voltage = decision["left_voltage"]
                right_voltage = decision["right_voltage"]
                self.drive.set_voltage(left_voltage, right_voltage)

                if self.debug_print:
                    print(
                        "raw={} black={} count={} pos={:.2f} found={} "
                        "strategy={} diff={:.2f}V left={:.2f}V right={:.2f}V".format(
                            raw_values,
                            black_flags,
                            decision["black_count"],
                            decision["position"],
                            1 if decision["line_found"] else 0,
                            decision["strategy"],
                            decision["correction"],
                            left_voltage,
                            right_voltage,
                        )
                    )

                time.sleep_ms(self.control_period_ms)
        except KeyboardInterrupt:
            print("Line tracking stopped.")
        finally:
            self.drive.stop()
            self.drive.close()
            print("Motors stopped.")
