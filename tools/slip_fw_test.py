#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка ПРОШИВОЧНОЙ правки слипа на сохранённых кадрах.

Зачем отдельно от slip_lab.py. Лаборатория проверяет ЗАМЫСЕЛ, а этот скрипт —
РЕАЛИЗАЦИЮ: он повторяет функции скетча буква в букву, с теми же константами
(старший байт первым, шаг по строкам 2, шаг по пикселям 2, запас 0.75, у
границы 1.0, окно добора 24, до 4 вставок) и со вторым защитным условием по
шершавости.

Именно такой проверки не хватило 25.09. Алгоритм был доказан в лаборатории, а
в скетч уехал с чтением младшим байтом вперёд — и правка начала вставлять
байты в здоровые кадры. На плате это стоило прогона: 491 «поражённый» кадр из
493, кадр раздулся до 11 КБ, потери чанков 31%.

Горизонтальная шершавость этого НЕ ЛОВИТ: сдвинутая картинка остаётся гладкой
по горизонтали. Ловит вертикальная гладкость, поэтому она здесь обязательная
часть проверки, а не украшение.

    python tools/slip_fw_test.py
"""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slip_lab import load_bmp565, median  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# --- константы скетча, один в один -----------------------------------------
CAM_REPAIR_ROW = 2
CAM_REPAIR_PIX = 2
CAM_REPAIR_MAX = 4
CAM_REPAIR_MARGIN = 0.75
CAM_REPAIR_FINE = 24
CAM_CHECK_ROW_STEP = 8          # шаг cam_roughness в скетче


def cam_rough_at(buf, off, npix, step):
    """Повтор cam_rough_at(): СТАРШИЙ БАЙТ ПЕРВЫЙ, как кладёт камера."""
    if npix < 2 or step < 1:
        return 0.0
    if off + npix * 2 > len(buf):
        npix = (len(buf) - off) // 2
        if npix < 2:
            return 0.0
    acc = 0
    n = 0
    prev = (buf[off] << 8) | buf[off + 1]
    for x in range(step, npix, step):
        i = off + x * 2
        cur = (buf[i] << 8) | buf[i + 1]
        dr = ((prev >> 11) & 0x1F) - ((cur >> 11) & 0x1F)
        dg = ((prev >> 5) & 0x3F) - ((cur >> 5) & 0x3F)
        db = (prev & 0x1F) - (cur & 0x1F)
        acc += (abs(dr) << 3) + (abs(dg) << 2) + (abs(db) << 3)
        n += 3
        prev = cur
    return acc / n if n else 0.0


def cam_shift_gain(buf, off, npix, step, margin):
    a = cam_rough_at(buf, off, npix, step)
    if a <= 0.0:
        return -1.0
    return a * margin - cam_rough_at(buf, off + 1, npix, step)


def cam_roughness(buf, w, h):
    """Повтор cam_roughness() из скетча — и он читает СТАРШИМ БАЙТОМ ВПЕРЁД.

    До 25.09 здесь было `(const uint16_t *)fb->buf`, то есть порядок платформы —
    младшим вперёд. Пока функция только мерила, расхождение было безвредным. Но
    она служит ВТОРЫМ УСЛОВИЕМ ОТКАТА, и там это оказалось смертельно: в
    съехавшем хвосте чтение младшим вперёд попадает «в такт», а после верной
    вставки выпадает, — откат срабатывал на КАЖДОЙ верной починке. Тест обязан
    воспроизводить эту функцию ровно такой, какая она в скетче.
    """
    acc = 0
    n = 0
    for y in range(0, h, CAM_CHECK_ROW_STEP):
        off = y * w * 2
        if off + w * 2 > len(buf):
            break
        prev = (buf[off] << 8) | buf[off + 1]
        for x in range(1, w):
            i = off + x * 2
            cur = (buf[i] << 8) | buf[i + 1]
            dr = ((prev >> 11) & 0x1F) - ((cur >> 11) & 0x1F)
            dg = ((prev >> 5) & 0x3F) - ((cur >> 5) & 0x3F)
            db = (prev & 0x1F) - (cur & 0x1F)
            acc += (abs(dr) << 3) + (abs(dg) << 2) + (abs(db) << 3)
            n += 3
            prev = cur
    return acc / n if n else 0.0


def cam_shift_votes(buf, w, h):
    votes = 0
    for y in range(0, h, CAM_REPAIR_ROW):
        off = y * w * 2
        if off + w * 2 + 2 > len(buf):
            break
        if cam_shift_gain(buf, off, w - 2, CAM_REPAIR_PIX, CAM_REPAIR_MARGIN) > 0.0:
            votes += 1
    return votes


def cam_transition_row(buf, w, h):
    for y in range(0, h, CAM_REPAIR_ROW):
        off = y * w * 2
        if off + w * 2 + 2 > len(buf):
            break
        if cam_shift_gain(buf, off, w - 2, CAM_REPAIR_PIX, CAM_REPAIR_MARGIN) <= 0.0:
            continue
        ny = y + CAM_REPAIR_ROW
        if ny < h:
            noff = ny * w * 2
            if (noff + w * 2 + 2 <= len(buf) and
                    cam_shift_gain(buf, noff, w - 2, CAM_REPAIR_PIX,
                                   CAM_REPAIR_MARGIN) <= 0.0):
                continue
        return y
    return -1


def cam_find_k(buf, w, lo, hi):
    guard = len(buf) - w * 2 - 4
    if guard < 2:
        return -1
    lo |= 1
    hi |= 1
    if hi > guard:
        hi = guard | 1
    if hi <= lo:
        return -1
    if cam_shift_gain(buf, hi, w, 1, 1.0) >= 0.0:
        return -1

    a, b = lo, hi
    while a + 2 < b:
        m = ((a + b) // 2) | 1
        if m <= a:
            break
        if cam_shift_gain(buf, m, w, 1, 1.0) < 0.0:
            b = m
        else:
            a = m + 2

    start = b - CAM_REPAIR_FINE * 8
    if start < lo:
        start = lo
    start |= 1
    q = start
    while q <= b:
        if cam_shift_gain(buf, q, CAM_REPAIR_FINE, 1, 1.0) < 0.0:
            return q
        q += 2
    return b


WHY = []


def cam_repair_slip(buf, w, h):
    """Повтор cam_repair_slip(). Возвращает (вставок, осталось строк)."""
    del WHY[:]
    votes = cam_shift_votes(buf, w, h)
    if votes == 0:
        return 0, 0
    inserts = 0

    for _ in range(CAM_REPAIR_MAX):
        r = cam_transition_row(buf, w, h)
        if r < 0:
            break
        lo = max(0, (r - 2) * w * 2)
        k = cam_find_k(buf, w, lo, (r + 3) * w * 2)
        if k < 0 or k + 1 >= len(buf):
            break

        rough_before = cam_roughness(buf, w, h)
        lost = buf[-1]
        filler = buf[k]
        buf[k + 1:] = buf[k:-1]
        buf[k] = filler

        nv = cam_shift_votes(buf, w, h)
        rough_after = cam_roughness(buf, w, h)
        if nv >= votes or rough_after > rough_before * 1.1 + 0.5:
            buf[k:-1] = buf[k + 1:]
            buf[-1] = lost
            WHY.append("строки %d->%d" % (votes, nv) if nv >= votes
                       else "шершавость %.2f->%.2f" % (rough_before, rough_after))
            break
        votes = nv
        inserts += 1
        if votes == 0:
            break
    return inserts, votes


def vert_rough(buf, w, h):
    """Вертикальная гладкость — метрика, которой правка НЕ управляет.

    Это главный контроль: вставка байта не туда оставляет картинку гладкой по
    горизонтали, но рвёт её по вертикали. Горизонтальная метрика такую порчу
    пропускает, вертикальная — нет.
    """
    acc = 0
    n = 0
    for y in range(1, h, 2):
        a, b = (y - 1) * w * 2, y * w * 2
        for x in range(0, w, 3):
            i, j = a + x * 2, b + x * 2
            if j + 1 >= len(buf):
                break
            p = (buf[i] << 8) | buf[i + 1]
            q = (buf[j] << 8) | buf[j + 1]
            acc += (abs(((p >> 11) & 31) - ((q >> 11) & 31)) << 3) \
                 + (abs(((p >> 5) & 63) - ((q >> 5) & 63)) << 2) \
                 + (abs((p & 31) - (q & 31)) << 3)
            n += 3
    return acc / n if n else 0.0


def main():
    files = [f for f in sorted(glob.glob(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "logs", "raw_*.bmp")))
        if "_fixed" not in f]
    if not files:
        print("кадров не найдено")
        return 1

    print("%-22s %8s %7s %8s %9s %9s  %s" %
          ("кадр", "строк_сдв", "вставок", "осталось", "вертик_до",
           "вертик_после", "вердикт"))
    print("-" * 104)

    untouched = fixed = part = damaged = 0
    for path in files:
        w, h, buf = load_bmp565(path, swap=False)
        v0 = cam_shift_votes(buf, w, h)
        vert0 = vert_rough(buf, w, h)
        ins, left = cam_repair_slip(buf, w, h)
        vert1 = vert_rough(buf, w, h)

        if ins == 0 and v0 == 0:
            verdict = "не тронут"
            untouched += 1
        elif vert1 > vert0 * 1.02:
            verdict = "!! ИСПОРЧЕН"
            damaged += 1
        elif ins == 0:
            verdict = "НЕ ТРОНУТ (откат)"
            part += 1
        elif left == 0:
            verdict = "вылечен"
            fixed += 1
        else:
            verdict = "улучшен"
            part += 1

        print("%-22s %8d %7d %8d %9.2f %9.2f  %s" %
              (os.path.basename(path).replace(".bmp", ""),
               v0, ins, left, vert0, vert1,
               verdict + (("  откат: " + WHY[0]) if WHY else "")))

    print("-" * 104)
    print("не тронуто %d, вылечено %d, улучшено %d, ИСПОРЧЕНО %d, всего %d"
          % (untouched, fixed, part, damaged, len(files)))
    if damaged:
        print("\nПРОВАЛ: правка ухудшила вертикальную гладкость. В прошивку нельзя.")
        return 1
    print("\nПРОЙДЕНО: ни один кадр не испорчен по независимой метрике.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
