"""Пишет порт платы в файл с метками времени, не дёргая DTR/RTS (плата не сбрасывается).
   python tools/serial_tap.py COM6 tools/logs/cam_usb_<тег>.txt"""
import sys, time, serial
port, out = sys.argv[1], sys.argv[2]
s = serial.Serial(); s.port = port; s.baudrate = 115200; s.timeout = 0.5; s.dtr = False; s.rts = False
s.open(); tail = b""
with open(out, "a", encoding="utf-8") as f:
    while True:
        try:
            b = s.read(4096)
        except serial.SerialException as e:
            f.write(f"{time.strftime('%H:%M:%S')} ПОРТ ПРОПАЛ: {e}\n"); f.flush(); break
        if not b:
            continue
        tail += b
        *lines, tail = tail.split(b"\n")
        ts = time.strftime("%H:%M:%S")
        for ln in lines:
            f.write(ts + " " + ln.decode("utf-8", "replace").rstrip("\r") + "\n")
        f.flush()
