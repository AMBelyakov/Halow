#!/usr/bin/env python3
"""
Разобрать CSV прогона с GAP_SWEEP и найти наименьшую паузу без брака.

    python tools/gap_sweep_report.py tools/logs/halow_..._gapsweep-broadcast.csv

ЧТО ЭТО МЕРИТ

Между чанками скетч делает паузу `CHUNK_GAP_MS`. Она нужна не «на всякий
случай»: за это время радио выгребает кольцо модуля. Не дать паузы — кольцо
переполнится, и байты пропадут ДО эфира. Дать слишком много — треть провода
уйдёт на молчание.

Рабочая точка — наименьшая пауза, при которой брак ещё нулевой. Признаки брака
(ими порог и подбирался): `ap_crc_err`, `ap_junk`, `frame_crc_err`.

ПОЧЕМУ СЧИТАЕМ ПО CSV, А НЕ ПО ПЕЧАТИ СКЕТЧА

Скетч сам печатает строку на каждую ступень, но в его собственном комментарии
оговорено, что цифры приблизительные: они опираются на отчёты приёмника по
обратному каналу, а тот глохнет, пока передатчик занимает эфир. В CSV счётчики
приходят по USB и не теряются.

КАК УЗНАЁМ ТЕКУЩУЮ ПАУЗУ

На время перебора скетч кладёт её в поле заголовка, которое доезжает до ПК как
столбец `sta_rssi` (в обычном режиме там ноль — `AT+RSSI` в прозрачном режиме
недоступен). То есть пауза видна построчно и не требует синхронизации часов.

ЗАЧЕМ СРАВНИВАТЬ ДВА ПРОГОНА

Пауза зависит от того, как быстро радио отдаёт кадр. Быстрее модуляция —
быстрее сток — меньше нужна пауза. Поэтому разница найденных порогов между
широковещательным и одноадресным прогоном и есть измеренный выигрыш
адаптивной модуляции, выраженный в миллисекундах простоя на каждый чанк.
"""

import argparse
import csv
import io
import sys


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


def num(r, k, d=0.0):
    try:
        return float(r.get(k) or d)
    except Exception:
        return d


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="+", help="один или несколько CSV прогонов")
    ap.add_argument("--settle", type=float, default=8.0,
                    help="сколько секунд после смены паузы не считать: "
                         "счётчики приёмника приходят с задержкой и на границе "
                         "ступени относятся ещё к прошлой")
    args = ap.parse_args()

    for path in args.csv:
        with io.open(path, encoding="utf-8", errors="replace") as f:
            rows = list(csv.DictReader(f))
        rows = [r for r in rows if num(r, "frames_d") > 0]
        if len(rows) < 10:
            print("%s: данных нет" % path)
            continue

        # Группируем по значению паузы, отбрасывая первые секунды каждой ступени.
        groups = {}
        change_t = num(rows[0], "t_s")
        prev_gap = num(rows[0], "sta_rssi", -1)
        for i in range(1, len(rows)):
            a, b = rows[i - 1], rows[i]
            gap = num(b, "sta_rssi", -1)
            if gap != prev_gap:
                change_t = num(b, "t_s")
                prev_gap = gap
                continue
            if num(b, "t_s") - change_t < args.settle:
                continue
            g = groups.setdefault(gap, dict(
                dt=0.0, frames=0.0, bytes=0.0, rx=0.0, ex=0.0,
                crc=0.0, junk=0.0, fcrc=0.0, lost=0.0))
            g["dt"] += num(b, "t_s") - num(a, "t_s")
            g["frames"] += num(b, "frames_ok") - num(a, "frames_ok")
            g["lost"] += num(b, "frames_lost") - num(a, "frames_lost")
            g["bytes"] += num(b, "bytes_total") - num(a, "bytes_total")
            g["rx"] += num(b, "chunks_rx") - num(a, "chunks_rx")
            g["ex"] += num(b, "chunks_exp") - num(a, "chunks_exp")
            g["crc"] += max(0.0, num(b, "ap_crc_err") - num(a, "ap_crc_err"))
            g["junk"] += max(0.0, num(b, "ap_junk") - num(a, "ap_junk"))
            g["fcrc"] += max(0.0, num(b, "frame_crc_err") - num(a, "frame_crc_err"))

        if not groups:
            print("%s: столбец sta_rssi пуст — прогон не с GAP_SWEEP?" % path)
            continue

        print("")
        print("=== %s ===" % path)
        print("%5s %6s %7s %7s %8s %9s %10s %9s" %
              ("пауза", "сек", "кадров", "fps", "кбит/с", "чанки,%",
               "ap_junk", "ap_crc"))
        clean = []
        for gap in sorted(groups, reverse=True):
            g = groups[gap]
            if g["dt"] < 20 or g["frames"] < 20:
                continue
            loss = 100.0 * (g["ex"] - g["rx"]) / g["ex"] if g["ex"] > 0 else 0.0
            bad = g["junk"] + g["crc"] + g["fcrc"]
            print("%3.0f мс %6.0f %7.0f %7.2f %8.1f %9.2f %10.0f %9.0f%s" %
                  (gap, g["dt"], g["frames"], g["frames"] / g["dt"],
                   g["bytes"] * 8 / 1000.0 / g["dt"], loss,
                   g["junk"], g["crc"], "" if bad else "   <- чисто"))
            if not bad:
                clean.append(gap)

        print("")
        if clean:
            print("НАИМЕНЬШАЯ ПАУЗА БЕЗ БРАКА: %.0f мс" % min(clean))
        else:
            print("ЧИСТЫХ СТУПЕНЕЙ НЕТ — брак на всех паузах, включая самую большую.")
            print("Значит дело не в паузе; смотреть радугу, шлейф, питание.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
