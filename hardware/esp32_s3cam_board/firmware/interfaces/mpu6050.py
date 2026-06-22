from machine import I2C, Pin
import struct


class MPU6050:
    """MPU6050 六轴姿态传感器驱动。"""

    def __init__(self, scl_pin, sda_pin, freq=400000, addr=0x68):
        self.i2c = I2C(0, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)
        self.addr = addr
        self._write(0x6B, 0x00)
        self._write(0x1C, 0x00)
        self._write(0x1B, 0x00)

        self.gx_off = 0.0
        self.gy_off = 0.0
        self.gz_off = 0.0
        self.ax_off = 0.0
        self.ay_off = 0.0
        self.az_off = 0.0
        self.az_scale = 1.0

    def _read(self, reg, n):
        return self.i2c.readfrom_mem(self.addr, reg, n)

    def _write(self, reg, v):
        self.i2c.writeto_mem(self.addr, reg, bytes([v]))

    def whoami(self):
        return self._read(0x75, 1)[0]

    def read_raw(self):
        a = self._read(0x3B, 6)
        g = self._read(0x43, 6)
        ax, ay, az = struct.unpack(">hhh", a)
        gx, gy, gz = struct.unpack(">hhh", g)
        return (ax / 16384.0, ay / 16384.0, az / 16384.0,
                gx / 131.0, gy / 131.0, gz / 131.0)

    def read(self):
        ax, ay, az, gx, gy, gz = self.read_raw()
        ax = ax - self.ax_off
        ay = ay - self.ay_off
        az = (az - self.az_off) * self.az_scale
        gx = gx - self.gx_off
        gy = gy - self.gy_off
        gz = gz - self.gz_off
        return ax, ay, az, gx, gy, gz

    def calibrate(self, samples=200):
        sum_ax = sum_ay = sum_az = 0.0
        sum_gx = sum_gy = sum_gz = 0.0
        for _ in range(samples):
            ax, ay, az, gx, gy, gz = self.read_raw()
            sum_ax += ax
            sum_ay += ay
            sum_az += az
            sum_gx += gx
            sum_gy += gy
            sum_gz += gz
        self.ax_off = sum_ax / samples
        self.ay_off = sum_ay / samples
        self.az_off = sum_az / samples - 1.0
        self.az_scale = 1.0 / (sum_az / samples - self.az_off)
        self.gx_off = sum_gx / samples
        self.gy_off = sum_gy / samples
        self.gz_off = sum_gz / samples
