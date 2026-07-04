import time


class LineTrackingApp:

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
                left_duty = decision["left_duty"]
                right_duty = decision["right_duty"]
                self.drive.set_duty(left_duty, right_duty)

                if self.debug_print:
                    print(
                        "raw={} black={} pos={:.2f} found={} dt={:.3f} L={} R={}".format(
                            raw_values,
                            black_flags,
                            decision["position"],
                            1 if decision["line_found"] else 0,
                            dt,
                            left_duty,
                            right_duty,
                        )
                    )

                time.sleep_ms(self.control_period_ms)
        except KeyboardInterrupt:
            print("Line tracking stopped.")
        finally:
            self.drive.stop()
            self.drive.close()
            print("Motors stopped.")
