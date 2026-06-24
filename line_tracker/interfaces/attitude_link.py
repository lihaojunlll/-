import time
from machine import UART


class AttitudeLink:
    """Read IMU and camera feedforward packets from the ESP32-S3 board."""

    def __init__(self, rx_pin, tx_pin, baudrate, timeout_ms=500,
                 debug_print=False):
        self.uart = UART(2, baudrate=baudrate, tx=tx_pin, rx=rx_pin)
        self.timeout_ms = timeout_ms
        self.debug_print = debug_print
        self.seq = 0
        self.pitch = 0.0
        self.roll = 0.0
        self.yaw = 0.0
        self.last_update_ms = 0
        self.cam_seq = 0
        self.cam_near = 0.0
        self.cam_far = 0.0
        self.cam_curve = 0.0
        self.cam_quality = 0.0
        self.last_cam_update_ms = 0
        self.lost_packets = 0
        self.cam_lost_packets = 0
        self.bad_packets = 0
        print("UART(2) attitude link: rx=GPIO%d tx=GPIO%d baud=%d" % (
            rx_pin, tx_pin, baudrate))

    def _checksum(self, text):
        value = 0
        for ch in text:
            value ^= ord(ch)
        return value & 0xFF

    def _split_and_check(self, raw):
        if "*" not in raw:
            return raw

        body, crc_text = raw.rsplit("*", 1)
        try:
            received = int(crc_text, 16)
        except ValueError:
            self.bad_packets += 1
            return None

        expected = self._checksum(body)
        if received != expected:
            self.bad_packets += 1
            if self.debug_print:
                print("UART_BAD_CRC,%s,%02X" % (raw, expected))
            return None
        return body

    def _parse_line(self, line):
        try:
            raw = line.decode().strip()
        except Exception:
            self.bad_packets += 1
            return False

        if not (raw.startswith("IMU,") or raw.startswith("CAM,")):
            return False

        body = self._split_and_check(raw)
        if body is None:
            return False

        if body.startswith("CAM,"):
            return self._parse_camera_body(body)
        return self._parse_imu_body(body)

    def _parse_imu_body(self, body):
        parts = body.split(",")
        if len(parts) != 5:
            self.bad_packets += 1
            return False

        try:
            seq = int(parts[1])
            pitch = float(parts[2])
            roll = float(parts[3])
            yaw = float(parts[4])
        except ValueError:
            self.bad_packets += 1
            return False

        if self.seq > 0 and seq > self.seq + 1:
            self.lost_packets += seq - self.seq - 1
            if self.debug_print:
                print("UART_LOST,%d,%d" % (self.seq + 1, seq - 1))

        self.seq = seq
        self.pitch = pitch
        self.roll = roll
        self.yaw = yaw
        self.last_update_ms = time.ticks_ms()

        if self.debug_print:
            print("UART_IMU,%d,%.2f,%.2f,%.2f" % (
                seq, pitch, roll, yaw))
        return True

    def _parse_camera_body(self, body):
        parts = body.split(",")
        if len(parts) != 6:
            self.bad_packets += 1
            return False

        try:
            seq = int(parts[1])
            near = float(parts[2])
            far = float(parts[3])
            curve = float(parts[4])
            quality = float(parts[5])
        except ValueError:
            self.bad_packets += 1
            return False

        if self.cam_seq > 0 and seq > self.cam_seq + 1:
            self.cam_lost_packets += seq - self.cam_seq - 1
            if self.debug_print:
                print("CAM_LOST,%d,%d" % (self.cam_seq + 1, seq - 1))

        self.cam_seq = seq
        self.cam_near = max(-1.0, min(1.0, near))
        self.cam_far = max(-1.0, min(1.0, far))
        self.cam_curve = max(-1.0, min(1.0, curve))
        self.cam_quality = max(0.0, min(1.0, quality))
        self.last_cam_update_ms = time.ticks_ms()

        if self.debug_print:
            print("UART_CAM,%d,%.2f,%.2f,%.2f,%.2f" % (
                seq, near, far, curve, quality))
        return True

    def update(self):
        updated = False
        while self.uart.any():
            line = self.uart.readline()
            if line:
                updated = self._parse_line(line) or updated
        return updated

    def is_fresh(self):
        if self.last_update_ms == 0:
            return False
        age = time.ticks_diff(time.ticks_ms(), self.last_update_ms)
        return age <= self.timeout_ms

    def is_camera_fresh(self):
        if self.last_cam_update_ms == 0:
            return False
        age = time.ticks_diff(time.ticks_ms(), self.last_cam_update_ms)
        return age <= self.timeout_ms

    def snapshot(self):
        return {
            "fresh": self.is_fresh(),
            "seq": self.seq,
            "pitch": self.pitch,
            "roll": self.roll,
            "yaw": self.yaw,
            "cam_fresh": self.is_camera_fresh(),
            "cam_seq": self.cam_seq,
            "cam_near": self.cam_near,
            "cam_far": self.cam_far,
            "cam_curve": self.cam_curve,
            "cam_quality": self.cam_quality,
            "lost_packets": self.lost_packets,
            "cam_lost_packets": self.cam_lost_packets,
            "bad_packets": self.bad_packets,
        }
