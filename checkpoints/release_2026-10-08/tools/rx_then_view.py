# -*- coding: utf-8 -*-
"""Дождаться, пока приёмник пропадёт (выдернули) и появится снова, затем запустить
логгер с заданной пометкой. Приёмник после перезапуска точки-камеры надо
переподключать, иначе не ассоциируется."""
import subprocess, sys, time
import serial.tools.list_ports as lp

RX = "9c:13:9e:b5:b3:c0"
note = sys.argv[1]


def rx_port():
    for p in lp.comports():
        if RX in (p.hwid or "").lower():
            return p.device
    return None


if rx_port():
    print("приёмник на месте — жду, пока выдернут", flush=True)
    while rx_port():
        time.sleep(0.5)
print("приёмника нет — жду появления", flush=True)
port = None
while not port:
    time.sleep(0.5)
    port = rx_port()
time.sleep(2)
print("приёмник на %s — запускаю логгер" % port, flush=True)
sys.exit(subprocess.call([sys.executable, "-u", r"D:\Halow\T-Halow\tools\halow_viewer.py",
                          "--serial-video", port, "--csv", "--note", note] + sys.argv[2:]))
