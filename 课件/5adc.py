from machine import ADC, Pin
import time


class PhotoelectricSampler:
    def __init__(self):
        self.adc_pins = {
            'adc1': 27,
            'adc2': 33,
            'adc3': 32,
            'adc4': 35,
            'adc5': 34
        }
        self.adc_objects = {}
        self._init_adc()
    
    def _init_adc(self):
        print("Initializing ADC channels...")
        
        for name, pin_num in self.adc_pins.items():
            try:
                adc = ADC(Pin(pin_num))
                adc.atten(ADC.ATTN_11DB)      # 输入范围 0-3.6V
                adc.width(ADC.WIDTH_12BIT)     # 12位分辨率 0-4095
                self.adc_objects[name] = adc
                print(f"  {name} (GPIO{pin_num}) initialized")
            except Exception as e:
                print(f"  {name} (GPIO{pin_num}) init failed: {e}")
    
    def read_all(self):
        """读取所有ADC通道"""
        results = {}
        for name, adc in self.adc_objects.items():
            try:
                value = adc.read()
                voltage = (value / 4095.0) * 3.6
                results[name] = {
                    'raw': value,
                    'voltage': voltage
                }
            except Exception as e:
                results[name] = {
                    'raw': -1,
                    'voltage': 0.0,
                    'error': str(e)
                }
        return results
    
    def print_samples(self, samples):
        """打印采样数据"""
        print("\n" + "="*60)
        print("Photoelectric sensor samples:")
        print("="*60)
        for name, data in samples.items():
            pin_num = self.adc_pins[name]
            if 'error' in data:
                print(f"{name} (GPIO{pin_num}): error={data['error']}")
            else:
                print(f"{name} (GPIO{pin_num}): raw={data['raw']:4d} | voltage={data['voltage']:.3f}V")
        print("="*60)
    
    def run_continuous(self, interval_ms=1000):
        """连续采样"""
        print(f"\nContinuous sampling started. Interval: {interval_ms}ms")
        print("Press Ctrl+C to stop\n")

        sample_count = 0
        try:
            while True:
                sample_count += 1
                print(f"\n--- Sample {sample_count} ---")
                
                samples = self.read_all()
                self.print_samples(samples)
                
                time.sleep_ms(interval_ms)
                
        except KeyboardInterrupt:
            print(f"\n\nSampling stopped. Total samples: {sample_count}")


def main():
    print("\n" + "="*60)
    print("ESP32 five-channel photoelectric sampler")
    print("="*60)
    
    # 创建采样器
    sampler = PhotoelectricSampler()
    
    # 进行一次初始采样
    print("\nRunning initial sample...")
    samples = sampler.read_all()
    sampler.print_samples(samples)
    
    # 开始连续采样（间隔500ms）
    sampler.run_continuous(interval_ms=500)


if __name__ == "__main__":
    main()
