from machine import ADC, I2C, Pin, PWM
import struct
import time
import car_config as config


class Motor:
    def __init__(self, in1, in2, enc_a, enc_b, encoder_sign=1):
        self.pwm1 = PWM(Pin(in1, Pin.OUT), freq=config.PWM_FREQ, duty=0)
        self.pwm2 = PWM(Pin(in2, Pin.OUT), freq=config.PWM_FREQ, duty=0)
        self.enc_a = Pin(enc_a, Pin.IN, Pin.PULL_UP)
        self.enc_b = Pin(enc_b, Pin.IN, Pin.PULL_UP)
        self.encoder_sign = encoder_sign
        self.count = 0
        self.last_pulse_us = time.ticks_us()
        # 过滤超过最大合理机械转速的异常脉冲。
        self.min_pulse_us = int(
            60000000 / (config.MAX_VALID_RPM * config.ENCODER_CPR)
        )
        self.enc_a.irq(trigger=Pin.IRQ_RISING, handler=self._encoder_irq)

    def _encoder_irq(self, pin):
        now = time.ticks_us()
        if time.ticks_diff(now, self.last_pulse_us) < self.min_pulse_us:
            return
        self.last_pulse_us = now
        direction = 1 if self.enc_b.value() else -1
        self.count += direction * self.encoder_sign

    def set_duty(self, duty):
        duty = max(-100.0, min(100.0, duty))
        raw = int(abs(duty) * 1023 / 100)
        if duty > 0:
            self.pwm1.duty(raw)
            self.pwm2.duty(0)
        elif duty < 0:
            self.pwm1.duty(0)
            self.pwm2.duty(raw)
        else:
            self.pwm1.duty(0)
            self.pwm2.duty(0)

    def stop(self):
        self.set_duty(0)

    def close(self):
        self.stop()
        self.enc_a.irq(handler=None)
        self.pwm1.deinit()
        self.pwm2.deinit()


class PhotoelectricSampler:
    def __init__(self):
        self.channels = []
        for name, pin_num in config.ADC_PINS:
            try:
                adc = ADC(Pin(pin_num))
                adc.atten(ADC.ATTN_11DB)
                adc.width(ADC.WIDTH_12BIT)
                self.channels.append((name, pin_num, adc))
                print("ADC_INIT,{},{},ok".format(name, pin_num))
            except Exception as error:
                print("ADC_INIT,{},{},error,{}".format(
                    name, pin_num, error
                ))

    def read_all(self):
        values = []
        for name, pin_num, adc in self.channels:
            try:
                raw = adc.read()
                voltage = raw * config.ADC_MAX_VOLTAGE / 4095.0
                values.append((name, pin_num, raw, voltage, "valid"))
            except Exception as error:
                values.append((name, pin_num, -1, 0.0, "error:{}".format(error)))
        return values


def raw_is_black(raw):
    if config.GRAY_BLACK_WHEN_BELOW_THRESHOLD:
        return raw <= config.GRAY_THRESHOLD
    return raw >= config.GRAY_THRESHOLD


def run_gray_monitor():
    print("=" * 64)
    print("ESP32 grayscale sensor real-time monitor")
    print("Motors are not initialized in this mode.")
    print("Threshold: raw {} {} -> black=1, white=0".format(
        "<=" if config.GRAY_BLACK_WHEN_BELOW_THRESHOLD else ">=",
        config.GRAY_THRESHOLD,
    ))
    print("=" * 64)
    print("格式：GRAY,采样序号,raw=[adc1,adc2,adc3,adc4,adc5],black=[adc1,adc2,adc3,adc4,adc5]")
    sampler = PhotoelectricSampler()
    sample_index = 0
    try:
        while True:
            sample_index += 1
            raw_values = []
            black_values = []
            for name, pin_num, raw, voltage, status in sampler.read_all():
                black = 1 if raw >= 0 and raw_is_black(raw) else 0
                raw_values.append(raw)
                black_values.append(black)
            print("GRAY,{},raw={},black={}".format(
                sample_index,
                raw_values,
                black_values,
            ))
            time.sleep_ms(config.GRAY_SAMPLE_INTERVAL_MS)
    except KeyboardInterrupt:
        print("\nGray sensor monitor stopped.")


class MPU6050:
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr
        self._w(0x6B, 0x00)
        self._w(0x1C, 0x00)
        self._w(0x1B, 0x00)

    def _r(self, reg, n):
        return self.i2c.readfrom_mem(self.addr, reg, n)

    def _w(self, reg, v):
        self.i2c.writeto_mem(self.addr, reg, bytes([v]))

    def read(self):
        a = self._r(0x3B, 6)
        g = self._r(0x43, 6)
        ax, ay, az = struct.unpack(">hhh", a)
        gx, gy, gz = struct.unpack(">hhh", g)
        return (ax / 16384.0, ay / 16384.0, az / 16384.0,
                gx / 131.0, gy / 131.0, gz / 131.0)


def run_i2c_scan():
    print("=" * 64)
    print("I2C scanner - find MPU6050 pins")
    print("=" * 64)
    pairs = [
        (22, 21), (21, 22), (18, 19), (19, 18),
        (26, 27), (25, 26), (23, 22),
        (16, 17), (5, 18), (14, 27),
    ]
    found = False
    for scl, sda in pairs:
        try:
            i2c = I2C(0, scl=Pin(scl), sda=Pin(sda), freq=100000)
            devs = i2c.scan()
            if devs:
                print("SCL=%2d SDA=%2d -> %s" % (scl, sda, [hex(d) for d in devs]))
                found = True
        except Exception as e:
            print("SCL=%2d SDA=%2d -> skip (%s)" % (scl, sda, e))
    if not found:
        print("No I2C devices found.")
    print("Scan complete.")


def run_mpu6050_monitor():
    scl = getattr(config, 'MPU6050_SCL', 22)
    sda = getattr(config, 'MPU6050_SDA', 21)
    print("=" * 64)
    print("MPU6050 monitor")
    print("I2C: SCL=GPIO%d, SDA=GPIO%d" % (scl, sda))
    print("=" * 64)

    i2c = I2C(0, scl=Pin(scl), sda=Pin(sda), freq=400000)
    devs = i2c.scan()
    print("I2C devices: %s" % [hex(d) for d in devs])

    if 0x68 not in devs:
        print("MPU6050 NOT FOUND at 0x68!")
        return

    imu = MPU6050(i2c)
    print("ax(g),ay(g),az(g),gx(dps),gy(dps),gz(dps)")
    print("-" * 52)
    try:
        while True:
            ax, ay, az, gx, gy, gz = imu.read()
            print("%.2f,%.2f,%.2f,%.1f,%.1f,%.1f" % (ax, ay, az, gx, gy, gz))
            time.sleep_ms(100)
    except KeyboardInterrupt:
        print("\nMPU6050 monitor stopped.")


def measure_rpm(motor):
    samples = []
    start_count = motor.count
    last_count = start_count
    last_time = time.ticks_ms()

    for sample_index in range(1, config.MOTOR_SAMPLE_COUNT + 1):
        time.sleep_ms(config.MOTOR_SAMPLE_INTERVAL_MS)
        now = time.ticks_ms()
        count = motor.count
        elapsed_ms = time.ticks_diff(now, last_time)
        delta_count = count - last_count
        if elapsed_ms > 0:
            rpm = delta_count * 60000.0 / (config.ENCODER_CPR * elapsed_ms)
            samples.append((sample_index, rpm, delta_count, elapsed_ms))
        last_count = count
        last_time = now

    total_ms = sum(sample[3] for sample in samples)
    total_count = motor.count - start_count
    rpm = (
        total_count * 60000.0 / (config.ENCODER_CPR * total_ms)
        if total_ms > 0
        else 0.0
    )
    valid = (
        abs(rpm) <= config.MAX_VALID_RPM
        and all(abs(sample[1]) <= config.MAX_VALID_RPM for sample in samples)
    )
    return rpm, samples, valid


def linear_fit(points):
    """拟合 转速 = 斜率 * 电压 + 截距。"""
    count = len(points)
    if count < 2:
        return None

    sum_x = sum(point[0] for point in points)
    sum_y = sum(point[1] for point in points)
    sum_xx = sum(point[0] * point[0] for point in points)
    sum_xy = sum(point[0] * point[1] for point in points)
    denominator = count * sum_xx - sum_x * sum_x
    if abs(denominator) < 1e-9:
        return None

    slope = (count * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / count

    mean_y = sum_y / count
    ss_total = sum((point[1] - mean_y) ** 2 for point in points)
    ss_residual = sum(
        (point[1] - (slope * point[0] + intercept)) ** 2
        for point in points
    )
    r_squared = 1.0 - ss_residual / ss_total if ss_total > 1e-9 else 1.0
    return slope, intercept, r_squared


def calibrate_direction(name, motor, direction):
    label = "forward" if direction > 0 else "reverse"
    measurements = []
    print("\nCalibrating {} {}...".format(name, label))
    print("motor,direction,duty,voltage,rpm")

    for duty in config.DUTY_STEPS:
        signed_duty = duty * direction
        motor.set_duty(signed_duty)
        time.sleep_ms(config.SETTLE_MS)
        rpm, samples, valid = measure_rpm(motor)
        voltage = config.SUPPLY_VOLTAGE * duty / 100.0
        speed_rpm = abs(rpm)
        status = "valid" if valid else "invalid"
        measurements.append((voltage, speed_rpm, duty, valid))
        for sample_index, sample_rpm, delta_count, elapsed_ms in samples:
            sample_valid = abs(sample_rpm) <= config.MAX_VALID_RPM
            print(
                "SAMPLE,{},{},{:.1f},{:.3f},{},{:.3f},{},{}".format(
                    name,
                    label,
                    signed_duty,
                    voltage,
                    sample_index,
                    sample_rpm,
                    delta_count,
                    "valid" if sample_valid else "invalid",
                )
            )
        print("{},{},{:.1f},{:.3f},{:.3f},{}".format(
            name, label, signed_duty, voltage, rpm, status
        ))

    motor.stop()
    time.sleep_ms(800)

    start_index = None
    for index in range(len(measurements) - config.START_CONFIRM_POINTS + 1):
        window = measurements[index:index + config.START_CONFIRM_POINTS]
        if all(item[1] >= config.START_RPM and item[3] for item in window):
            start_index = index
            break

    if start_index is None:
        print("ERROR: {} {} did not start reliably.".format(name, label))
        return None

    start_voltage = measurements[start_index][0]
    print("START_VOLTAGE {} {}: {:.4f} V".format(
        name, label, start_voltage
    ))
    fit_points = [
        (voltage, rpm)
        for voltage, rpm, duty, valid in measurements[start_index:]
        if valid and rpm >= config.START_RPM
    ]
    fit = linear_fit(fit_points)
    if fit is None:
        print("ERROR: not enough valid samples for {} {}.".format(name, label))
        return None

    slope, intercept, r_squared = fit
    if slope <= 0 or r_squared < config.MIN_FIT_R2:
        print(
            "ERROR: rejected fit for {} {}: slope={:.6f}, R2={:.5f}".format(
                name, label, slope, r_squared
            )
        )
        return None

    dead_voltage = max(0.0, -intercept / slope) if slope > 0 else 0.0
    print(
        "FIT {} {}: rpm = {:.6f} * voltage + {:.6f}, R2 = {:.5f}".format(
            name, label, slope, intercept, r_squared
        )
    )
    print(
        "INVERSE {} {}: voltage = (target_rpm - ({:.6f})) / {:.6f}".format(
            name, label, intercept, slope
        )
    )
    print("ESTIMATED_DEAD_VOLTAGE {} {}: {:.4f} V".format(
        name, label, dead_voltage
    ))
    return slope, intercept, r_squared


def print_config(name, forward_fit, reverse_fit):
    print("\n# 将这些数值填入你的转速控制程序：")
    for label, fit in (("FORWARD", forward_fit), ("REVERSE", reverse_fit)):
        if fit:
            slope, intercept, r_squared = fit
            print("{}_{}_SLOPE = {:.9f}".format(name.upper(), label, slope))
            print("{}_{}_INTERCEPT = {:.9f}".format(
                name.upper(), label, intercept
            ))


def calibrate_motor(name, motor):
    forward_fit = calibrate_direction(name, motor, 1)
    reverse_fit = calibrate_direction(name, motor, -1)
    print_config(name, forward_fit, reverse_fit)


def run_motor_calibration():
    motor1 = Motor(13, 15, 16, 17)
    motor2 = Motor(14, 25, 18, 19)
    print("=" * 64)
    print("ESP32 motor voltage-speed calibration")
    print("Equivalent voltage = {:.2f} V * PWM duty".format(config.SUPPLY_VOLTAGE))
    print("Encoder CPR = {}".format(config.ENCODER_CPR))
    print("Duty step = 5%, samples per point = {}".format(config.MOTOR_SAMPLE_COUNT))
    print("Maximum accepted speed = {:.1f} RPM".format(config.MAX_VALID_RPM))
    print("Lift the car before starting. Each wheel is tested separately.")
    print("=" * 64)

    try:
        calibrate_motor("motor1", motor1)
        calibrate_motor("motor2", motor2)
        print("\nCalibration complete.")
    except KeyboardInterrupt:
        print("\nCalibration stopped.")
    finally:
        motor1.close()
        motor2.close()
        print("Motors stopped and PWM released.")


def main():
    mode = config.TEST_MODE.lower()
    print("TEST_MODE={}".format(mode))
    if mode == "gray":
        run_gray_monitor()
    elif mode == "motor":
        run_motor_calibration()
    elif mode == "i2c_scan":
        run_i2c_scan()
    elif mode == "mpu6050":
        run_mpu6050_monitor()
    else:
        raise ValueError("Unknown TEST_MODE: {}".format(config.TEST_MODE))


if __name__ == "__main__":
    main()
