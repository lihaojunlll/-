from machine import ADC, Pin

from Config import TractionConfig


class Traction:
    """五路模拟灰度传感器的底层驱动。"""

    def __init__(self, pins=TractionConfig.ADC_PINS):
        if len(pins) != 5:
            raise ValueError("Traction requires exactly five ADC pins")

        self.pins = tuple(pins)
        self._sensors = []

        # 使用 11 dB 衰减和 12 位精度读取较宽范围的模拟电压。
        for pin_number in self.pins:
            adc = ADC(Pin(pin_number))
            adc.atten(ADC.ATTN_11DB)
            adc.width(ADC.WIDTH_12BIT)
            self._sensors.append(adc)

    def read(self):
        """按最左侧到最右侧的顺序读取五路 ADC 原始值。"""
        return tuple(sensor.read() for sensor in self._sensors)

    def read_raw(self):
        """兼容旧测试代码的原始值读取接口。"""
        return self.read()

    def read_voltage(self):
        """返回按左到右排列的近似电压值。"""
        return tuple(value * 3.6 / 4095 for value in self.read())
