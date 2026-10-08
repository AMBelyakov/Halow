#!/usr/bin/env python3
"""
Снять кадры из работающего просмотрщика и посчитать долю поражённых радугой.

    python tools/frame_check.py --count 300
    python tools/frame_check.py --count 60 --save tools/logs/proba

ЧТО ЭТО МЕРИТ

Радуга на этом стенде — это байтовый слип: в сыром RGB565 сетка пикселей
съезжает на один байт посреди кадра, старший и младший байты меняются ролями, и
плавные переходы превращаются в цветные контуры. Глазами это видно, но «видно»
не число, а для диплома нужно число.

Признак слипа — РЕЗКИЙ РОСТ РАЗНИЦЫ МЕЖДУ СОСЕДНИМИ ПИКСЕЛЯМИ ПО ГОРИЗОНТАЛИ.
Съехавшая сетка делает картинку «шершавой»: соседние пиксели, которые в
исходнике почти одинаковы, начинают отличаться на десятки единиц. Меряем
среднюю разницу между соседними пикселями в строке и называем её грубостью.

По замерам 15.09:

    чистый кадр      грубость 3.6-4.5, максимум на 502 чистых кадрах 5.50
    поражённый       грубость 12-21

Порог 8.0 лежит посередине широкого зазора, поэтому решение устойчиво и не
зависит от сюжета.

ВАЖНО: это НЕ универсальная мера качества. Очень мелкий контрастный сюжет
(текст, жалюзи, клавиатура во весь кадр) поднимает грубость сам по себе. Мерить
надо на том же сюжете, что и раньше, иначе сравнение бессмысленно — 15.09 на
этом уже обожглись: камеру подвинули между прогонами, и доля радуги
«выросла» без всякой связи с правками.

ПОЧЕМУ ЧЕРЕЗ ПРОСМОТРЩИК, А НЕ DUMP_RAW

`DUMP_RAW` снимает кадр до сжатия, но рвёт поток: синхронная выгрузка 84 КБ в
USB встаёт намертво, если её никто не разгребает, и захват падает до 0.3 fps.
Здесь же мы идём по уже работающему тракту приёмника и на камере не трогаем
ничего.

ПРЕДУСЛОВИЕ: запущен `tools/halow_viewer.py --serial-video COM7` и видео идёт.
"""

import argparse
import io
import os
import sys
import time
import urllib.request


def _console_utf8():
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


_console_utf8()

SOI = b"\xff\xd8"
EOI = b"\xff\xd9"


def grab(url, count, timeout):
    """Достать `count` JPEG из MJPEG-потока. Возвращает список байтовых строк."""
    out = []
    buf = b""
    deadline = time.time() + timeout
    r = urllib.request.urlopen(url, timeout=10)
    try:
        while len(out) < count and time.time() < deadline:
            chunk = r.read(8192)
            if not chunk:
                break
            buf += chunk
            # Режем по маркерам начала и конца изображения.
            while True:
                i = buf.find(SOI)
                if i < 0:
                    buf = buf[-1:]
                    break
                j = buf.find(EOI, i + 2)
                if j < 0:
                    buf = buf[i:]
                    break
                out.append(buf[i:j + 2])
                buf = buf[j + 2:]
                if len(out) >= count:
                    break
    finally:
        try:
            r.close()
        except Exception:
            pass
    return out


def roughness(jpeg_bytes):
    """Средняя разница между соседними пикселями по горизонтали."""
    from PIL import Image
    import numpy as np
    im = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    a = np.asarray(im, dtype=np.int16)
    if a.shape[1] < 2:
        return 0.0
    return float(np.abs(a[:, 1:, :] - a[:, :-1, :]).mean())


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8099/stream.mjpg")
    ap.add_argument("--count", type=int, default=200,
                    help="сколько кадров снять")
    ap.add_argument("--threshold", type=float, default=8.0,
                    help="порог грубости, выше которого кадр считается поражённым")
    ap.add_argument("--timeout", type=float, default=180,
                    help="сколько секунд максимум снимать")
    ap.add_argument("--save", metavar="ПРЕФИКС",
                    help="сохранить худшие и лучшие кадры под этим префиксом")
    args = ap.parse_args()

    print("снимаю до %d кадров с %s" % (args.count, args.url))
    sys.stdout.flush()
    frames = grab(args.url, args.count, args.timeout)
    if not frames:
        print("НИ ОДНОГО КАДРА. Просмотрщик запущен и видео идёт?")
        return 2

    vals = []
    for f in frames:
        try:
            vals.append((roughness(f), len(f), f))
        except Exception:
            pass
    if not vals:
        print("кадры пришли, но ни один не раскодировался")
        return 2

    vals.sort(key=lambda x: x[0])
    bad = [v for v in vals if v[0] > args.threshold]
    n = len(vals)
    med = vals[n // 2][0]
    avg_sz = sum(v[1] for v in vals) / float(n)

    print("")
    print("кадров разобрано:      %d" % n)
    print("грубость: мин %.2f  медиана %.2f  макс %.2f (порог %.1f)" %
          (vals[0][0], med, vals[-1][0], args.threshold))
    print("средний размер кадра:  %.0f байт" % avg_sz)
    print("")
    print("ПОРАЖЕНО РАДУГОЙ: %d из %d = %.1f%%" % (len(bad), n, 100.0 * len(bad) / n))
    if not bad:
        print("(ни одного кадра выше порога — картинка чистая)")

    if args.save:
        d = os.path.dirname(args.save)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        keep = vals[-3:] + vals[:3]
        for k, (r, sz, data) in enumerate(keep):
            p = "%s_%02d_rough%05.2f.jpg" % (args.save, k, r)
            io.open(p, "wb").write(data)
        print("")
        print("сохранено 6 кадров (три худших и три лучших): %s_*.jpg" % args.save)
    return 0


if __name__ == "__main__":
    sys.exit(main())
