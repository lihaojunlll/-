import math
import time


class AttitudeEstimator:
    """互补滤波姿态解算。"""

    def __init__(self, alpha=0.96):
        self.alpha = alpha
        self.pitch = 0.0
        self.roll = 0.0
        self.yaw = 0.0
        self.last_ms = time.ticks_ms()

    def _wrap(self, angle):
        return ((angle + 180.0) % 360.0) - 180.0

    def update(self, ax, ay, az, gx, gy, gz):
        now = time.ticks_ms()
        dt = time.ticks_diff(now, self.last_ms) / 1000.0
        self.last_ms = now

        acc_pitch = math.atan2(-ax, math.sqrt(ay * ay + az * az)) * 57.2958
        acc_roll = math.atan2(ay, az) * 57.2958

        self.pitch = self.alpha * (self.pitch + gx * dt) + (1.0 - self.alpha) * acc_pitch
        self.roll = self.alpha * (self.roll + gy * dt) + (1.0 - self.alpha) * acc_roll
        self.yaw += gz * dt

        self.pitch = self._wrap(self.pitch)
        self.roll = self._wrap(self.roll)
        self.yaw = self._wrap(self.yaw)

        return self.pitch, self.roll, self.yaw
