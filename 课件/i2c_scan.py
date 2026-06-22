from machine import I2C, Pin
pairs = [(22,21),(21,22),(18,19),(19,18),(33,32),(26,27),(25,26)]
for scl, sda in pairs:
    try:
        i2c = I2C(0, scl=Pin(scl), sda=Pin(sda), freq=100000)
        devs = i2c.scan()
        print("SCL=%d SDA=%d -> %s" % (scl, sda, [hex(d) for d in devs]))
    except Exception as e:
        print("SCL=%d SDA=%d -> ERROR: %s" % (scl, sda, e))
