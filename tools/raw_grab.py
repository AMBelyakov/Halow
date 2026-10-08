#!/usr/bin/env python3
"""
Ловит сырые кадры RGB565 из USB платы с камерой и сохраняет их картинками.

Зачем. Всё, что видно в просмотрщике, прошло через сжатие, радио и сборку.
Сырой кадр — это байты, которые камера положила в память. Если они битые, то
рисунок порчи прямо называет механизм:

    мусор подряд с какой-то строки до конца  -> оборвался DMA
    битая каждая вторая / через равный шаг    -> сбой тактирования (PCLK)
    отдельные пиксели вразброс                -> помеха на шине, шлейф
    кусок в середине, дальше снова нормально  -> буфер перезаписали чужим кадром

    python tools/raw_grab.py COM6            # поймать 5 кадров
    python tools/raw_grab.py COM6 -n 20      # поймать 20

Кадры сохраняются в tools/logs/raw_*.bmp — BMP открывается в Windows без
сторонних программ. Плюс скрипт сам печатает разбор по строкам, чтобы не
пришлось разглядывать глазами.

Скетч камеры должен быть собран с DUMP_RAW 1.
"""

import argparse
import os
import struct
import sys
import time

SYNC = b"\xA5\x5A"


def crc16(data, crc=0xFFFF):
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def big_crc(data):
    """Та же схема, что big_crc() в скетче: куски по 32 КБ, между ними сдвиг."""
    acc = 0
    for off in range(0, len(data), 32768):
        acc ^= crc16(data[off:off + 32768])
        acc = ((acc << 1) | (acc >> 15)) & 0xFFFF
    return acc


def rgb565_rows(data, w, h, swap):
    """Разворачивает кадр в список строк по (r, g, b)."""
    rows = []
    for y in range(h):
        row = []
        base = y * w * 2
        for x in range(w):
            i = base + x * 2
            if swap:
                v = data[i] | (data[i + 1] << 8)
            else:
                v = (data[i] << 8) | data[i + 1]
            r = (v >> 11) & 0x1F
            g = (v >> 5) & 0x3F
            b = v & 0x1F
            row.append((r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2))
        rows.append(row)
    return rows


def save_bmp(path, rows, w, h):
    """24-битный BMP без библиотек. Строки в BMP идут снизу вверх."""
    pad = (4 - (w * 3) % 4) % 4
    body = bytearray()
    for y in range(h - 1, -1, -1):
        for (r, g, b) in rows[y]:
            body += bytes((b, g, r))
        body += b"\x00" * pad
    size = 54 + len(body)
    hdr = struct.pack("<2sIHHI", b"BM", size, 0, 0, 54)
    hdr += struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(body), 2835, 2835, 0, 0)
    with open(path, "wb") as f:
        f.write(hdr)
        f.write(body)


def analyse(rows, w, h):
    """
    Ищет битые строки. Признак: соседние строки настоящего изображения похожи,
    а строка из мусора резко отличается от обеих соседок. Считаем среднюю
    разницу с предыдущей строкой и печатаем те, где она выбивается.
    """
    diffs = []
    for y in range(1, h):
        a, b = rows[y - 1], rows[y]
        s = 0
        # шаг 4 по горизонтали — точности хватает, считается вчетверо быстрее
        for x in range(0, w, 4):
            s += abs(a[x][0] - b[x][0]) + abs(a[x][1] - b[x][1]) + abs(a[x][2] - b[x][2])
        diffs.append(s / (w / 4 * 3))

    ordered = sorted(diffs)
    typical = ordered[len(ordered) // 2]          # медиана — «обычная» строка
    limit = max(12.0, typical * 4)
    bad = [y + 1 for y, d in enumerate(diffs) if d > limit]

    print("    строк всего %d, обычная разница между соседними %.1f, порог %.1f"
          % (h, typical, limit))
    if not bad:
        print("    БИТЫХ СТРОК НЕ НАЙДЕНО — кадр целый")
        return

    print("    подозрительных строк: %d из %d" % (len(bad), h))
    # Сжимаем список в диапазоны, чтобы увидеть узор
    ranges = []
    start = prev = bad[0]
    for y in bad[1:]:
        if y == prev + 1:
            prev = y
            continue
        ranges.append((start, prev))
        start = prev = y
    ranges.append((start, prev))
    print("    участки: " + ", ".join(
        ("%d" % a) if a == b else ("%d-%d" % (a, b)) for a, b in ranges[:20]))

    # Подсказка по узору
    if len(ranges) == 1 and ranges[0][1] >= h - 2:
        print("    УЗОР: сплошной блок до конца кадра -> похоже на обрыв DMA")
    elif len(ranges) > h / 8 and all(a == b for a, b in ranges):
        step = [ranges[i + 1][0] - ranges[i][0] for i in range(min(6, len(ranges) - 1))]
        print("    УЗОР: одиночные строки с шагом %s -> похоже на сбой тактирования" % step)
    elif len(ranges) == 1:
        print("    УЗОР: один блок в середине -> похоже на перезапись буфера")
    else:
        print("    УЗОР: разрозненные участки -> похоже на помеху по шине (шлейф)")


def main():
    ap = argparse.ArgumentParser(description="Ловит сырые кадры камеры T-Halow")
    ap.add_argument("port", help="COM-порт платы с камерой, например COM6")
    ap.add_argument("-n", type=int, default=5, help="сколько кадров поймать")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--swap", action="store_true",
                    help="переставить байты в пикселе, если цвета выглядят дико")
    args = ap.parse_args()

    try:
        import serial
    except ImportError:
        print("нужен pyserial: pip install pyserial")
        return

    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(outdir, exist_ok=True)

    with serial.Serial(args.port, args.baud, timeout=1) as ser:
        # pyserial поднимает DTR/RTS, а на ESP32 они ведут на RESET/BOOT.
        ser.dtr = False
        ser.rts = False
        print("слушаю %s, жду %d кадров (скетч должен быть с DUMP_RAW 1)"
              % (args.port, args.n))

        buf = bytearray()
        caught = 0
        stamp = time.strftime("%H%M%S")

        while caught < args.n:
            chunk = ser.read(16384)
            if chunk:
                buf.extend(chunk)

            while True:
                i = buf.find(SYNC)
                if i < 0:
                    if len(buf) > 1:
                        del buf[:-1]
                    break
                if len(buf) < i + 11:
                    break
                kind = buf[i + 2]
                if kind not in (ord("R"), ord("J")):
                    del buf[:i + 2]      # чужая запись или текст лога
                    continue
                w, h = struct.unpack_from("<HH", buf, i + 3)
                ln = struct.unpack_from("<I", buf, i + 7)[0]
                if kind == ord("R"):
                    if ln != w * h * 2 or ln > 4 * 1024 * 1024:
                        del buf[:i + 2]
                        continue
                else:
                    # JPEG: размеры в заголовке нулевые, длина произвольная
                    if ln < 128 or ln > 512 * 1024:
                        del buf[:i + 2]
                        continue
                if len(buf) < i + 11 + ln + 2:
                    break

                data = bytes(buf[i + 11:i + 11 + ln])
                crc_got = struct.unpack_from("<H", buf, i + 11 + ln)[0]
                del buf[:i + 11 + ln + 2]

                crc_calc = big_crc(data)
                ok = (crc_calc == crc_got)
                crc_txt = ("совпала" if ok else
                           "РАЗОШЛАСЬ (%04X против %04X) — испорчено при выгрузке"
                           % (crc_calc, crc_got))

                if kind == ord("J"):
                    # JPEG идёт сразу за сырым кадром и сделан ИЗ НЕГО, так что
                    # это прямая пара для сравнения.
                    path = os.path.join(outdir, "raw_%s_%02d.jpg" % (stamp, caught))
                    with open(path, "wb") as f:
                        f.write(data)
                    print("    JPEG из того же кадра: %d байт, CRC %s" % (ln, crc_txt))
                    print("    сохранён %s" % path)
                    continue

                caught += 1
                print("\nкадр %d: %dx%d, %d байт, CRC %s" % (caught, w, h, ln, crc_txt))

                rows = rgb565_rows(data, w, h, args.swap)
                path = os.path.join(outdir, "raw_%s_%02d.bmp" % (stamp, caught))
                save_bmp(path, rows, w, h)
                print("    сохранён %s" % path)
                analyse(rows, w, h)

    print("\nготово. Картинки в %s" % outdir)


if __name__ == "__main__":
    main()
