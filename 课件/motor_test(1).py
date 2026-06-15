from machine import Pin, PWM
import time
import math
import _thread

SINE_FREQ = 0.1
SAMPLE_RATE = 50
PWM_FREQ = 20000
MAX_SPEED = 100
ENCODER_CPR = 60

pin_m1_in1 = Pin(13, Pin.OUT)
pin_m1_in2 = Pin(15, Pin.OUT)
pwm_m1_in1 = PWM(pin_m1_in1, freq=PWM_FREQ, duty=0)
pwm_m1_in2 = PWM(pin_m1_in2, freq=PWM_FREQ, duty=0)

pin_m2_in1 = Pin(14, Pin.OUT)
pin_m2_in2 = Pin(25, Pin.OUT)
pwm_m2_in1 = PWM(pin_m2_in1, freq=PWM_FREQ, duty=0)
pwm_m2_in2 = PWM(pin_m2_in2, freq=PWM_FREQ, duty=0)

pin_enc1_a = Pin(16, Pin.IN, Pin.PULL_UP)
pin_enc1_b = Pin(17, Pin.IN, Pin.PULL_UP)
pin_enc2_a = Pin(18, Pin.IN, Pin.PULL_UP)
pin_enc2_b = Pin(19, Pin.IN, Pin.PULL_UP)

encoder1_counter = 0
encoder2_counter = 0
last_enc1_a = pin_enc1_a.value()
last_enc2_a = pin_enc2_a.value()

def encoder1_callback(pin):
    global encoder1_counter, last_enc1_a
    current_a = pin_enc1_a.value()
    current_b = pin_enc1_b.value()
    
    if current_a != last_enc1_a and current_a == 1:
        if current_b == 0:
            encoder1_counter -= 1
        else:
            encoder1_counter += 1
    
    last_enc1_a = current_a

def encoder2_callback(pin):
    global encoder2_counter, last_enc2_a
    current_a = pin_enc2_a.value()
    current_b = pin_enc2_b.value()
    
    if current_a != last_enc2_a and current_a == 1:
        if current_b == 0:
            encoder2_counter -= 1
        else:
            encoder2_counter += 1
    
    last_enc2_a = current_a

pin_enc1_a.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=encoder1_callback)
pin_enc2_a.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=encoder2_callback)

def set_motor1_speed(speed):
    if speed > 0:
        pwm_m1_in1.duty(int(speed * 1023 / 100))
        pwm_m1_in2.duty(0)
    elif speed < 0:
        pwm_m1_in1.duty(0)
        pwm_m1_in2.duty(int(abs(speed) * 1023 / 100))
    else:
        pwm_m1_in1.duty(0)
        pwm_m1_in2.duty(0)

def set_motor2_speed(speed):
    if speed > 0:
        pwm_m2_in1.duty(int(speed * 1023 / 100))
        pwm_m2_in2.duty(0)
    elif speed < 0:
        pwm_m2_in1.duty(0)
        pwm_m2_in2.duty(int(abs(speed) * 1023 / 100))
    else:
        pwm_m2_in1.duty(0)
        pwm_m2_in2.duty(0)

def read_encoders():
    global encoder1_counter, encoder2_counter
    enc1 = encoder1_counter
    enc2 = encoder2_counter
    return enc1, enc2

def main():
    print("=" * 60)
    print("ESP32 dual motor sine speed test")
    print("=" * 60)
    print(f"Sine frequency: {SINE_FREQ} Hz")
    print(f"Control rate: {SAMPLE_RATE} Hz")
    print(f"PWM frequency: {PWM_FREQ} Hz")
    print(f"Encoder CPR: {ENCODER_CPR}")
    print("=" * 60)
    print("Motor1: PWM=G13,G15 | Encoder=G16,G17")
    print("Motor2: PWM=G14,G25 | Encoder=G18,G19")
    print("=" * 60)
    
    start_time = time.ticks_ms()
    last_print_time = start_time
    print_interval = 200
    
    last_enc1 = 0
    last_enc2 = 0
    
    try:
        while True:
            current_time = time.ticks_ms()
            elapsed = (current_time - start_time) / 1000.0
            
            speed1 = int(MAX_SPEED * math.sin(2 * math.pi * SINE_FREQ * elapsed))
            speed2 = int(MAX_SPEED * math.sin(2 * math.pi * SINE_FREQ * elapsed + math.pi))
            
            set_motor1_speed(speed1)
            set_motor2_speed(speed2)
            
            if time.ticks_diff(current_time, last_print_time) >= print_interval:
                enc1, enc2 = read_encoders()
                
                delta_enc1 = enc1 - last_enc1
                delta_enc2 = enc2 - last_enc2
                
                rpm1 = (delta_enc1 / ENCODER_CPR) * (30000 / print_interval)
                rpm2 = (delta_enc2 / ENCODER_CPR) * (30000 / print_interval)
                
                dir1 = "FWD" if delta_enc1 >= 0 else "REV"
                dir2 = "FWD" if delta_enc2 >= 0 else "REV"
                
                print(f"time={elapsed:.2f}s | motor1: speed={speed1:4d}%, dir={dir1:3s}, encoder={enc1:6d}, rpm={rpm1:6.1f} | motor2: speed={speed2:4d}%, dir={dir2:3s}, encoder={enc2:6d}, rpm={rpm2:6.1f}")
                
                last_print_time = current_time
                last_enc1 = enc1
                last_enc2 = enc2
            
            time.sleep_ms(1000 // SAMPLE_RATE)
    
    except KeyboardInterrupt:
        print("\nTest stopped")
        set_motor1_speed(0)
        set_motor2_speed(0)
        pwm_m1_in1.deinit()
        pwm_m1_in2.deinit()
        pwm_m2_in1.deinit()
        pwm_m2_in2.deinit()
        pin_enc1_a.irq(handler=None)
        pin_enc2_a.irq(handler=None)
        print("Motors stopped. PWM released.")

if __name__ == "__main__":
    main()
