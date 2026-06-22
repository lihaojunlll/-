import config
import time
from algorithms.attitude import AttitudeEstimator
from interfaces.mpu6050 import MPU6050


def main():
    print("S3CAM started.")

    imu = MPU6050(
        scl_pin=config.MPU6050_SCL_PIN,
        sda_pin=config.MPU6050_SDA_PIN,
        freq=config.MPU6050_I2C_FREQ,
    )
    print("MPU6050 WHO_AM_I: 0x%02X" % imu.whoami())
    imu.calibrate(200)

    cam = None
    if config.CAMERA_ENABLED:
        from interfaces.camera import Camera
        cam = Camera(pins={
            "xclk": config.CAMERA_XCLK_PIN,
            "pclk": config.CAMERA_PCLK_PIN,
            "vsync": config.CAMERA_VSYNC_PIN,
            "href": config.CAMERA_HREF_PIN,
            "sda": config.CAMERA_SDA_PIN,
            "scl": config.CAMERA_SCL_PIN,
            "data": config.CAMERA_DATA_PINS,
        })
        cam.init()
        print("Camera initialized.")

    attitude = AttitudeEstimator(alpha=config.ATTITUDE_ALPHA)

    print(" Accel(m/s2)        Gyro(dps)        Attitude(deg)")
    print(" X     Y     Z      X    Y    Z     Pitch  Roll   Yaw")
    print("------ ------ ------ ---- ---- ---- ------ ------ ------")

    while True:
        ax, ay, az, gx, gy, gz = imu.read()
        pitch, roll, yaw = attitude.update(ax, ay, az, gx, gy, gz)

        if config.DEBUG_PRINT:
            parts = [
                "%6.2f %6.2f %6.2f %5.1f %5.1f %5.1f %6.1f %6.1f %6.1f" % (
                    ax * 9.8, ay * 9.8, az * 9.8,
                    gx, gy, gz, pitch, roll, yaw),
            ]
            if cam is not None:
                try:
                    img = cam.capture()
                    parts.append("frame:%dx%d" % (img.width(), img.height()))
                except Exception as e:
                    parts.append("cam_err:%s" % e)
            print(" ".join(parts))

        time.sleep_ms(config.CONTROL_PERIOD_MS)


if __name__ == "__main__":
    main()
