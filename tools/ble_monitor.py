"""BLE serial monitor for ESP32 CAR-DEBUG.

Connects to the Nordic UART Service (NUS) on the ESP32 and prints
all debug telemetry to the console, just like a serial monitor.

Usage:
    python tools/ble_monitor.py [DEVICE_NAME]

Requires:
    pip install bleak
"""

import asyncio
import sys

from bleak import BleakScanner, BleakClient

NUS_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
NUS_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
DEFAULT_NAME = "CAR-DEBUG"


async def main(target_name=DEFAULT_NAME):
    print("Scanning for BLE devices...")

    device = None
    devices = await BleakScanner.discover(timeout=5.0, return_adv=True)
    for d, adv_data in devices.values():
        name = adv_data.local_name or d.name or ""
        if target_name.lower() in name.lower():
            device = d
            print("Found: %s (%s) RSSI=%d" % (name, d.address, adv_data.rssi))
            break

    if device is None:
        print("Device '%s' not found. Available devices:" % target_name)
        for d, adv_data in devices.values():
            name = adv_data.local_name or d.name or ""
            if name:
                print("  - %s (%s)" % (name, d.address))
        return

    buf = ""

    def notification_handler(sender, data):
        nonlocal buf
        buf += data.decode("utf-8", errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            print(line, flush=True)

    print("Connecting to %s..." % device.address)
    async with BleakClient(device) as client:
        if not client.is_connected:
            print("Failed to connect.")
            return

        print("Connected. Waiting for data...\n")
        await client.start_notify(NUS_TX_CHAR_UUID, notification_handler)

        try:
            while client.is_connected:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass

        await client.stop_notify(NUS_TX_CHAR_UUID)
        print("\nDisconnected.")


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_NAME
    asyncio.run(main(name))
