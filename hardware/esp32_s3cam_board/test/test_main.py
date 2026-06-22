from machine import I2C, Pin
import struct
import time
import math


class MPU6050:
    def __init__(self, i2c):
        self.i2c = i2c
        self._w(0x6B, 0x00)
        self._w(0x1C, 0x00)
        self._w(0x1B, 0x00)
        self.gx_off = self.gy_off = self.gz_off = 0.0
        self.ax_off = self.ay_off = self.az_off = 0.0
        self.az_scale = 1.0

    def _r(self, reg, n):
        return self.i2c.readfrom_mem(0x68, reg, n)

    def _w(self, reg, v):
        self.i2c.writeto_mem(0x68, reg, bytes([v]))

    def read_raw(self):
        a = self._r(0x3B, 6)
        g = self._r(0x43, 6)
        ax, ay, az = struct.unpack(">hhh", a)
        gx, gy, gz = struct.unpack(">hhh", g)
        return (ax / 16384.0, ay / 16384.0, az / 16384.0,
                gx / 131.0, gy / 131.0, gz / 131.0)

    def read(self):
        ax, ay, az, gx, gy, gz = self.read_raw()
        return (ax - self.ax_off, ay - self.ay_off,
                (az - self.az_off) * self.az_scale,
                gx - self.gx_off, gy - self.gy_off, gz - self.gz_off)

    def calibrate(self, n=200):
        sgx = sgy = sgz = 0.0
        sax = say = saz = 0.0
        for _ in range(n):
            ax, ay, az, gx, gy, gz = self.read_raw()
            sax += ax; say += ay; saz += az
            sgx += gx; sgy += gy; sgz += gz
            time.sleep_ms(5)
        self.ax_off = sax / n
        self.ay_off = say / n
        self.az_off = saz / n - 1.0
        self.az_scale = 1.0 / (saz / n - self.az_off)
        self.gx_off = sgx / n
        self.gy_off = sgy / n
        self.gz_off = sgz / n
        print("IMU calibrated.")


def main():
    mode = TEST_MODE.lower()
    if mode != "mpu6050":
        print("Unknown TEST_MODE: %s" % TEST_MODE)
        return

    print("=" * 52)
    print("MPU6050 Attitude Monitor")
    print("=" * 52)

    i2c = I2C(0, scl=Pin(MPU6050_SCL), sda=Pin(MPU6050_SDA), freq=400000)
    devs = i2c.scan()
    print("Devices: %s" % [hex(d) for d in devs])
    if 0x68 not in devs:
        print("MPU6050 NOT FOUND!")
        return

    imu = MPU6050(i2c)
    imu.calibrate(200)

    alpha = 0.96
    pitch = roll = yaw = 0.0
    last = time.ticks_ms()

    print("")
    print(" Accel(m/s2)      Gyro(dps)       Attitude(deg)")
    print(" X     Y     Z     X    Y    Z    Pitch Roll  Yaw")
    print("------ ------ ----- ---- ---- ---- ----- ----- -----")

    while True:
        ax, ay, az, gx, gy, gz = imu.read()
        now = time.ticks_ms()
        dt = time.ticks_diff(now, last) / 1000.0
        last = now

        ap = math.atan2(-ax, math.sqrt(ay * ay + az * az)) * 57.2958
        ar = math.atan2(ay, az) * 57.2958
        pitch = alpha * (pitch + gx * dt) + (1 - alpha) * ap
        roll = alpha * (roll + gy * dt) + (1 - alpha) * ar
        yaw += gz * dt
        pitch = ((pitch + 180) % 360) - 180
        roll = ((roll + 180) % 360) - 180
        yaw = ((yaw + 180) % 360) - 180

        print("%6.2f %6.2f %5.2f %5.1f %5.1f %5.1f %5.1f %5.1f %5.1f" % (
            ax * 9.8, ay * 9.8, az * 9.8, gx, gy, gz, pitch, roll, yaw))
        time.sleep_ms(10)


if __name__ == "__main__":
    main()
