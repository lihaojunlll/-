import time
from machine import UART


class LineTrackingApp:
    """正式寻迹应用主循环。"""

    def __init__(self, sensors, drive, policy, control_period_ms,
                 uart_rx_pin, uart_tx_pin, uart_baudrate,
                 debug_print=True):
        self.sensors = sensors
        self.drive = drive
        self.policy = policy
        self.control_period_ms = control_period_ms
        self.debug_print = debug_print
        self.uart = UART(2, baudrate=uart_baudrate,
                         tx=uart_tx_pin, rx=uart_rx_pin)
        self.attitude_pitch = 0.0
        self.attitude_roll = 0.0
        self.attitude_yaw = 0.0
        self.last_imu_seq = 0
        print("UART(2) init: rx=GPIO%d tx=GPIO%d baud=%d" % (
            uart_rx_pin, uart_tx_pin, uart_baudrate))

    def _read_attitude(self):
        while self.uart.any():
            try:
                line = self.uart.readline()
                if line and line.startswith(b"IMU,"):
                    raw = line.decode().strip()
                    parts = raw.split(",")
                    if len(parts) == 5:
                        seq = int(parts[1])
                        self.attitude_pitch = float(parts[2])
                        self.attitude_roll = float(parts[3])
                        self.attitude_yaw = float(parts[4])
                        print("UART_RECV,%d,%.2f,%.2f,%.2f" % (
                            seq,
                            self.attitude_pitch,
                            self.attitude_roll,
                            self.attitude_yaw,
                        ))
                        if (self.last_imu_seq > 0 and
                                seq != self.last_imu_seq + 1):
                            lost_start = self.last_imu_seq + 1
                            lost_end = seq - 1
                            if lost_start == lost_end:
                                print("UART_LOST,%d" % lost_start)
                            else:
                                print("UART_LOST,%d,%d" % (
                                    lost_start, lost_end))
                        self.last_imu_seq = seq
            except Exception:
                pass

    def run(self):
        print("Line tracking app started.")
        last_time = time.ticks_ms()

        try:
            while True:
                now = time.ticks_ms()
                dt = time.ticks_diff(now, last_time) / 1000.0
                last_time = now

                self._read_attitude()

                raw_values, black_flags = self.sensors.read()
                decision = self.policy.decide(black_flags, dt)
                left_voltage = decision["left_voltage"]
                right_voltage = decision["right_voltage"]
                self.drive.set_voltage(left_voltage, right_voltage)

                if self.debug_print:
                    print(
                        "raw={} black={} count={} pos={:.2f} found={} "
                        "strategy={} diff={:.2f}V left={:.2f}V right={:.2f}V "
                        "imu={:.1f},{:.1f},{:.1f}".format(
                            raw_values,
                            black_flags,
                            decision["black_count"],
                            decision["position"],
                            1 if decision["line_found"] else 0,
                            decision["strategy"],
                            decision["correction"],
                            left_voltage,
                            right_voltage,
                            self.attitude_pitch,
                            self.attitude_roll,
                            self.attitude_yaw,
                        )
                    )

                time.sleep_ms(self.control_period_ms)
        except KeyboardInterrupt:
            print("Line tracking stopped.")
        finally:
            self.drive.stop()
            self.drive.close()
            print("Motors stopped.")
