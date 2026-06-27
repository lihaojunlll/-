try:
    import bluetooth
    _BLE_AVAILABLE = True
except ImportError:
    try:
        import ubluetooth as bluetooth
        _BLE_AVAILABLE = True
    except ImportError:
        _BLE_AVAILABLE = False


class BLEDebug:
    """BLE UART debug transmitter using Nordic UART Service (NUS).

    Mobile apps like "Serial Bluetooth Terminal" or "nRF Connect" can
    connect and receive the same debug telemetry printed to UART.
    """

    _UART_SVC_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
    _UART_TX_UUID = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")
    _UART_RX_UUID = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")

    def __init__(self, name="CAR-DEBUG", enabled=True):
        self._enabled = enabled and _BLE_AVAILABLE
        self._name = name
        self._connected = False
        self._conn_handle = None
        self._tx_handle = None

        if not _BLE_AVAILABLE:
            if enabled:
                print("BLE: bluetooth module not available, BLE disabled.")
            return

        if not self._enabled:
            return

        try:
            self._ble = bluetooth.BLE()
            self._ble.active(True)
            self._ble.config(gap_name=name)
            self._setup_service()
            self._ble.irq(self._irq_handler)
            self._start_advertising()
            print("BLE debug: advertising as '%s'" % name)
        except Exception as e:
            print("BLE: init failed: %s" % e)
            self._enabled = False

    def _setup_service(self):
        tx_char = (self._UART_TX_UUID, bluetooth.FLAG_NOTIFY)
        rx_char = (self._UART_RX_UUID, bluetooth.FLAG_WRITE)
        service = (self._UART_SVC_UUID, (tx_char, rx_char))
        ((self._tx_handle, _),) = self._ble.gatts_register_services((service,))
        self._ble.gatts_set_buffer(self._tx_handle, 512)

    def _irq_handler(self, event, data):
        if event == 1:
            self._connected = True
            self._conn_handle, _, _ = data
            print("BLE: connected")
        elif event == 2:
            self._connected = False
            self._conn_handle = None
            print("BLE: disconnected")
            self._start_advertising()

    def _start_advertising(self):
        payload = self._adv_payload()
        self._ble.gap_advertise(100000, adv_data=payload)

    def _adv_payload(self):
        name_bytes = self._name.encode()
        payload = bytearray()
        payload.extend(b'\x02\x01\x06')
        payload.append(len(name_bytes) + 1)
        payload.append(0x09)
        payload.extend(name_bytes)
        return payload

    def send(self, text):
        if not self._enabled or not self._connected:
            return
        try:
            data = (text + "\n").encode()
            chunk = 20
            for i in range(0, len(data), chunk):
                self._ble.gatts_notify(
                    self._conn_handle, self._tx_handle, data[i:i + chunk])
        except Exception:
            pass

    def is_connected(self):
        return self._connected
