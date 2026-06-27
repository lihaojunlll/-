import network
import time


def connect(ssid, password, timeout=15, hostname="",
            static_ip="", static_mask="", static_gw="", static_dns=""):
    """Connect to WiFi as STA. Returns IP string or None on failure.

    WiFi is deactivated on failure to free ADC2 for sensor reading.
    """
    wlan = network.WLAN(network.STA_IF)

    if not ssid:
        wlan.active(False)
        return None

    wlan.active(True)

    if hostname:
        try:
            wlan.config(hostname=hostname)
        except Exception:
            pass

    if wlan.isconnected():
        return wlan.ifconfig()[0]

    if static_ip and static_mask and static_gw and static_dns:
        wlan.ifconfig((static_ip, static_mask, static_gw, static_dns))

    try:
        ssid_bytes = ssid.encode()
    except Exception:
        ssid_bytes = ssid

    print("WiFi: connecting to '%s'..." % ssid)
    wlan.connect(ssid_bytes, password)
    deadline = time.time() + timeout
    while not wlan.isconnected():
        if time.time() > deadline:
            print("WiFi: connection timeout, WiFi deactivated.")
            wlan.active(False)
            return None
        time.sleep(0.5)

    ip = wlan.ifconfig()[0]
    print("WiFi: connected, IP=%s" % ip)
    return ip


def start_webrepl(password):
    """Start WebREPL server with the given password."""
    if not password:
        return
    try:
        import webrepl
        webrepl.start(password=password)
        print("WebREPL: started on ws://<ip>:8266/")
    except Exception as e:
        print("WebREPL: start failed - %s" % e)
