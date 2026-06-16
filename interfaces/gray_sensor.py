from machine import ADC, Pin


class GraySensorArray:
    """5 路灰度传感器接口。"""

    def __init__(self, pins, thresholds, black_when_below=True,
                 max_voltage=3.6, enabled_mask=None):
        self.thresholds = thresholds
        self.black_when_below = black_when_below
        self.max_voltage = max_voltage
        self.enabled_mask = enabled_mask
        self.adc_list = []

        for pin_num in pins:
            adc = ADC(Pin(pin_num))
            adc.atten(ADC.ATTN_11DB)
            adc.width(ADC.WIDTH_12BIT)
            self.adc_list.append(adc)

    def read_raw(self):
        return [adc.read() for adc in self.adc_list]

    def read_voltage(self):
        raw_values = self.read_raw()
        return [value * self.max_voltage / 4095.0 for value in raw_values]

    def raw_to_black_flags(self, raw_values):
        flags = []
        for index, raw in enumerate(raw_values):
            if self.enabled_mask is not None and not self.enabled_mask[index]:
                flags.append(0)
                continue
            threshold = self.thresholds[index]
            if self.black_when_below:
                flags.append(1 if raw <= threshold else 0)
            else:
                flags.append(1 if raw >= threshold else 0)
        return flags

    def read(self):
        raw_values = self.read_raw()
        black_flags = self.raw_to_black_flags(raw_values)
        return raw_values, black_flags
