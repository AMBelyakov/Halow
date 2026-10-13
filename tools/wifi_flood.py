"""Замер ёмкости канала Wi-Fi 2,4 ГГц (13.10): заливка вместо видео.

Приёмник (WifiVideoTest_RX) по команде `w <секунд>` просит камеру лить пакеты по 1400 байт
без пауз и раз в секунду печатает строку
    FLOOD t=… rx_kbps=… pkts=… lost=… rssi=…
Скрипт шлёт команду, собирает эти строки и лог камеры (записи 'L': «ЗАЛИВКА: отправлено …»),
пишет всё в tools/logs/wifi_flood_ДАТА_ВРЕМЯ_метка.txt и печатает итог.
Просмотрщик на время замера закрыть: порт один.

    python tools/wifi_flood.py --port COM7 --seconds 60 --note 5m_14dbm
"""
import argparse
import os
import re
import statistics as st
import sys
import time

import serial

FLOOD_RE = re.compile(r"FLOOD t=(\d+) rx_kbps=(\d+) pkts=(\d+) lost=(\d+) rssi=(-?\d+)")


def records(buf):
    """Выбирает из потока записи A5 5A type len crc payload; остальное — текст."""
    text = bytearray()
    logs = []
    i = 0
    while i < len(buf):
        if buf[i] == 0xA5 and i + 7 <= len(buf) and buf[i + 1] == 0x5A:
            n = buf[i + 3] | (buf[i + 4] << 8)
            if i + 7 + n > len(buf):
                break
            if buf[i + 2] == ord("L") and n > 2:
                logs.append(bytes(buf[i + 9:i + 7 + n]).decode("utf-8", "ignore"))
            i += 7 + n
            continue
        text.append(buf[i])
        i += 1
    return text.decode("utf-8", "ignore"), logs, bytes(buf[i:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM7")
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    os.makedirs("tools/logs", exist_ok=True)
    name = "tools/logs/wifi_flood_%s%s.txt" % (time.strftime("%Y%m%d_%H%M%S"),
                                              ("_" + a.note) if a.note else "")
    # Без DTR/RTS: иначе открытие порта перезапускает приёмник, и команда уходит в плату,
    # которая ещё не подключилась к камере (первый запуск 13.10 так и пропал).
    s = serial.Serial()
    s.port, s.baudrate, s.timeout = a.port, 115200, 0.2
    s.dtr = False
    s.rts = False
    s.open()
    t_wait = time.time() + 30
    seen = b""
    while time.time() < t_wait:
        seen = (seen + s.read(65536))[-4096:]
        m = re.findall(rb'"conn":(\d)', seen)
        if m and m[-1] == b"1":
            break
    else:
        print("приёмник не сообщил о связи с камерой за 30 с")
        return 1
    s.write(b"w %d\n" % a.seconds)
    t_end = time.time() + a.seconds + 6
    buf = b""
    tail = ""
    rows, cam = [], []
    with open(name, "w", encoding="utf-8") as out:
        while time.time() < t_end:
            buf += s.read(65536)
            text, logs, buf = records(buf)
            tail += text
            *lines, tail = tail.split("\n")
            for ln in lines:
                m = FLOOD_RE.search(ln)
                if m:
                    r = tuple(int(x) for x in m.groups())
                    rows.append(r)
                    out.write(ln.strip() + "\n")
                    print("приём %5d кбит/с  пакетов %4d  пропусков %3d  rssi %d" % r[1:])
            for ln in logs:
                if "ЗАЛИВКА" in ln or "WIFI" in ln:
                    cam.append(ln.strip())
                    out.write("CAM " + ln.strip() + "\n")
                    print("  камера:", ln.strip())
        s.write(b"w 0\n")
        s.close()
        if not rows:
            print("строк FLOOD нет — заливка не пошла")
            return 1
        k = [r[1] for r in rows[1:-1]] or [r[1] for r in rows]
        pk = sum(r[2] for r in rows)
        lost = sum(r[3] for r in rows)
        rs = [r[4] for r in rows if r[4]]
        res = ("ИТОГ %s: приём медиана %d кбит/с (мин %d, макс %d), пропусков %.2f %% (%d из %d), "
               "rssi медиана %s" % (a.note, st.median(k), min(k), max(k),
                                    100.0 * lost / max(1, pk + lost), lost, pk + lost,
                                    st.median(rs) if rs else "—"))
        out.write(res + "\n")
    print(res)
    print("лог:", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
