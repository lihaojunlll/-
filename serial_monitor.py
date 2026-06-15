import argparse
import codecs
import signal
import sys
import time

import serial

try:
    import msvcrt
except ImportError:
    msvcrt = None


def configure_console():
    """将本机终端配置为 UTF-8，无法配置时继续使用当前编码。"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_args():
    parser = argparse.ArgumentParser(description="ESP32 UTF-8 串口监视器")
    parser.add_argument("--port", required=True, help="串口名称，例如 COM5")
    parser.add_argument("--baud", type=int, default=115200, help="串口波特率")
    return parser.parse_args()


def run_monitor(port, baud):
    """
    读取 ESP32 串口数据。

    增量解码器会保留数据块末尾不完整的 UTF-8 字符，等下一块数据到达后
    再进行解码，避免 mpremote 在 Windows 上出现 UnicodeDecodeError。
    """
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    with serial.Serial(port, baudrate=baud, timeout=0.02) as device:
        print("已连接到 {}，波特率 {}。".format(port, baud))
        print("按 Ctrl+] 退出，按 Ctrl+C 中断板上程序，按 Ctrl+D 软复位。")

        def interrupt_device(signum, frame):
            device.write(b"\x03")

        signal.signal(signal.SIGINT, interrupt_device)

        while True:
            waiting = device.in_waiting
            if waiting:
                data = device.read(waiting)
                text = decoder.decode(data, final=False)
                if text:
                    sys.stdout.write(text)
                    sys.stdout.flush()

            if msvcrt is not None and msvcrt.kbhit():
                key = msvcrt.getwch()

                if key == "\x1d":
                    break

                # Windows 功能键由两个字符组成，本监视器不向板子转发功能键。
                if key in ("\x00", "\xe0"):
                    if msvcrt.kbhit():
                        msvcrt.getwch()
                    continue

                device.write(key.encode("utf-8"))

            time.sleep(0.005)

        remaining = decoder.decode(b"", final=True)
        if remaining:
            sys.stdout.write(remaining)
        print("\n串口监视器已退出。")


def main():
    configure_console()
    args = parse_args()

    try:
        run_monitor(args.port, args.baud)
    except serial.SerialException as error:
        print("串口连接失败：{}".format(error))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
