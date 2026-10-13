"""Мощность теста Wi-Fi 2,4 ГГц на обеих платах (13.10): приёмник шлёт её и камере.

    python tools/wifi_power.py --port COM7 --dbm 20

Порт открывается без DTR/RTS (иначе приёмник перезапускается), команда уходит после того,
как приёмник сообщит о связи с камерой; в ответ ждём строку камеры «МОЩНОСТЬ: N дБм».
"""
import argparse
import re
import sys
import time

import serial


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM7")
    ap.add_argument("--dbm", type=int, required=True)
    a = ap.parse_args()
    s = serial.Serial()
    s.port, s.baudrate, s.timeout = a.port, 115200, 0.3
    s.dtr = False
    s.rts = False
    s.open()
    t = time.time() + 40
    b = b""
    while time.time() < t:
        b = (b + s.read(8192))[-4096:]
        m = re.findall(rb'"conn":(\d)', b)
        if m and m[-1] == b"1":
            break
    else:
        print("приёмник не сообщил о связи с камерой за 40 с")
        return 1
    time.sleep(3)          # камера должна успеть получить hello и знать адрес приёмника
    s.write(b"p %d\n" % a.dbm)
    t = time.time() + 12
    b = b""
    while time.time() < t:
        b += s.read(65536)
    s.close()
    ok = re.findall(rb"\xd0\x9c\xd0\x9e\xd0\xa9\xd0\x9d\xd0\x9e\xd0\xa1\xd0\xa2\xd0\xac: (\d+)", b)  # «МОЩНОСТЬ: »
    wifi = re.findall(rb"WIFI [^\n]*", b)
    print("камера подтвердила:", [int(x) for x in ok] or "нет")
    for w in wifi[-2:]:
        print(w.decode("utf-8", "ignore"))
    return 0 if ok and int(ok[-1]) == a.dbm else 1


if __name__ == "__main__":
    sys.exit(main())
