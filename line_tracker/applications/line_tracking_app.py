import time


class LineTrackingApp:

    def __init__(self, sensors, drive, policy, control_period_ms,
                 debug_print=True, attitude_link=None):
        self.sensors = sensors
        self.drive = drive
        self.policy = policy
        self.control_period_ms = control_period_ms
        self.debug_print = debug_print
        self.attitude_link = attitude_link

    def run(self):
        print("Line tracking app started.")
        last_time = time.ticks_ms()
        last_print_ms = 0

        try:
            while True:
                now = time.ticks_ms()
                dt = time.ticks_diff(now, last_time) / 1000.0
                last_time = now

                camera = None
                if self.attitude_link:
                    self.attitude_link.update()
                    camera = self.attitude_link.snapshot()

                raw_values, black_flags = self.sensors.read()
                decision = self.policy.decide(black_flags, dt, camera)
                left_duty = decision["left_duty"]
                right_duty = decision["right_duty"]
                self.drive.set_duty(left_duty, right_duty)

                if self.debug_print and time.ticks_diff(now, last_print_ms) >= 200:
                    last_print_ms = now
                    cam_str = ""
                    if camera and camera.get("cam_fresh"):
                        cam_str = "cam_q={:.2f} slow={:.2f} turn={} ".format(
                            camera.get("cam_quality", 0),
                            camera.get("cam_slowdown", 0),
                            camera.get("cam_turn", 0))
                    print(
                        "raw={} black={} pos={:.2f} found={} {}scale={:.2f} ff={} dt={:.3f} L={} R={}".format(
                            raw_values,
                            black_flags,
                            decision["position"],
                            1 if decision["line_found"] else 0,
                            cam_str,
                            decision["camera_speed_scale"],
                            decision["camera_turn_ff"],
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
