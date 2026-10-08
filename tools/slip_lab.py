#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Лаборатория байтового слипа: разбор и починка НА СОХРАНЁННЫХ кадрах.

Зачем отдельный инструмент. Две попытки чинить слип прямо в прошивке (25.09)
испортили кадры обе: критерий срабатывал на контрастных сюжетах и выбрасывал
байт из здорового кадра. Проверять алгоритм на живом потоке нельзя — там нет
эталона и нет отката. Здесь эталон есть: те же кадры, тот же алгоритм, и видно
поимённо, что он сделал с каждым.

Механизм порчи (разобран 15.09). В сыром RGB565 с некоторого байтового
смещения k теряется один байт. Дальше до конца кадра старший и младший байты
меняются ролями, пиксельная сетка съезжает — отсюда «радуга». Строки при этом
целы, разрывов нет, поэтому проверки на рвань ничего не находили.

Починка: вставить обратно один байт на позицию k. Значение вставленного байта
неважно — это один пиксель, его не видно.

    python tools/slip_lab.py                    # разобрать все кадры в logs
    python tools/slip_lab.py tools/logs/raw_013041_06.bmp
    python tools/slip_lab.py --save             # сохранить починенные BMP
"""

import argparse
import glob
import os
import struct
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


# ---------------------------------------------------------------- загрузка

def load_bmp565(path, swap=False):
    """
    BMP -> (w, h, bytearray в формате RGB565).

    raw_grab.py делал 565 -> 888 размножением битов (r<<3 | r>>2), а это
    обратимо: старшие 5/6/5 бит вернут исходное слово ровно. Так что из BMP
    восстанавливаются ТЕ ЖЕ байты, которые камера положила в память.
    """
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] != b"BM":
        raise ValueError("не BMP: %s" % path)
    off = struct.unpack_from("<I", raw, 10)[0]
    w, h = struct.unpack_from("<ii", raw, 18)
    bits = struct.unpack_from("<H", raw, 28)[0]
    if bits != 24:
        raise ValueError("ожидался 24-битный BMP, а тут %d" % bits)
    pad = (4 - (w * 3) % 4) % 4
    stride = w * 3 + pad

    buf = bytearray(w * h * 2)
    for y in range(h):
        src = off + (h - 1 - y) * stride        # в BMP строки снизу вверх
        dst = y * w * 2
        for x in range(w):
            b, g, r = raw[src + x * 3], raw[src + x * 3 + 1], raw[src + x * 3 + 2]
            v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            if swap:
                buf[dst + x * 2] = v & 0xFF
                buf[dst + x * 2 + 1] = v >> 8
            else:
                buf[dst + x * 2] = v >> 8
                buf[dst + x * 2 + 1] = v & 0xFF
    return w, h, buf


def save_bmp565(path, buf, w, h, swap=False):
    pad = (4 - (w * 3) % 4) % 4
    body = bytearray()
    for y in range(h - 1, -1, -1):
        base = y * w * 2
        for x in range(w):
            i = base + x * 2
            if i + 1 >= len(buf):
                body += b"\x00\x00\x00"
                continue
            v = (buf[i] | (buf[i + 1] << 8)) if swap else ((buf[i] << 8) | buf[i + 1])
            r, g, b = (v >> 11) & 0x1F, (v >> 5) & 0x3F, v & 0x1F
            body += bytes((b << 3 | b >> 2, g << 2 | g >> 4, r << 3 | r >> 2))
        body += b"\x00" * pad
    hdr = struct.pack("<2sIHHI", b"BM", 54 + len(body), 0, 0, 54)
    hdr += struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(body), 2835, 2835, 0, 0)
    with open(path, "wb") as f:
        f.write(hdr)
        f.write(body)


# ------------------------------------------------------------- шершавость

def rough_at(buf, byte_off, npix, swap=False, step=1):
    """
    Средняя разница между соседними пикселями по горизонтали, начиная с
    ПРОИЗВОЛЬНОГО байтового смещения. Смещение произвольное, а не кратное
    двум, — в этом весь смысл: так проверяется гипотеза «а если бы здесь был
    вставлен байт», ничего не меняя в данных.

    Шкала совпадает с cam_roughness() в скетче: 5 и 6 бит растянуты до 8.
    """
    if npix < 2:
        return 0.0
    end = byte_off + npix * 2
    if end > len(buf):
        npix = (len(buf) - byte_off) // 2
        if npix < 2:
            return 0.0
    acc = 0
    n = 0
    i = byte_off
    if swap:
        prev = buf[i] | (buf[i + 1] << 8)
    else:
        prev = (buf[i] << 8) | buf[i + 1]
    for x in range(step, npix, step):
        i = byte_off + x * 2
        cur = (buf[i] | (buf[i + 1] << 8)) if swap else ((buf[i] << 8) | buf[i + 1])
        dr = ((prev >> 11) & 0x1F) - ((cur >> 11) & 0x1F)
        dg = ((prev >> 5) & 0x3F) - ((cur >> 5) & 0x3F)
        db = (prev & 0x1F) - (cur & 0x1F)
        acc += (abs(dr) << 3) + (abs(dg) << 2) + (abs(db) << 3)
        n += 3
        prev = cur
    return acc / n if n else 0.0


def row_roughness(buf, w, h, swap=False, step=1):
    return [rough_at(buf, y * w * 2, w, swap, step) for y in range(h)]


def median(v):
    s = sorted(v)
    return s[len(s) // 2] if s else 0.0


# ---------------------------------------------------------------- поиск k
#
# Главная мысль: порог не нужен вовсе. В целой части кадра обычное чтение
# ровнее сдвинутого, в испорченной — наоборот. Сравниваются две величины
# ОДНОГО И ТОГО ЖЕ участка, поэтому контрастный сюжет поднимает обе разом и
# решения не меняет. Ровно на абсолютном пороге погорели версии 1 и 2.

MARGIN = 0.75          # сдвиг должен выигрывать уверенно, а не на волос


def shifted_wins(buf, off, npix, swap=False, step=1, margin=MARGIN):
    """
    Уверенно ли чтение со сдвигом ровнее обычного.

    Запас нужен вот зачем: на контрастном сюжете обе величины большие и близкие,
    и сравнение «хоть на сколько-нибудь» превращается в подбрасывание монеты.
    Требуем перевеса в четверть — тогда решают только настоящие слипы.
    """
    a = rough_at(buf, off, npix, swap, step)
    b = rough_at(buf, off + 1, npix, swap, step)
    return (a * margin) - b if a > 0 else -1.0


def shift_votes(buf, w, h, swap=False, step=2):
    """Сколько строк уверенно читаются со сдвигом. Это и есть мера порчи."""
    n = 0
    for y in range(0, h, step):
        off = y * w * 2
        if off + w * 2 + 2 > len(buf):
            break
        if shifted_wins(buf, off, w - 2, swap) > 0:
            n += 1
    return n


def find_transition_row(buf, w, h, swap=False, coarse=2):
    """
    Первая строка, начиная с которой выигрывает сдвинутое чтение.
    Возвращает (строка, база по целому началу) или (None, база).
    """
    base_rows = []
    y = 0
    while y < h:
        off = y * w * 2
        if off + w * 2 + 2 > len(buf):
            break
        if shifted_wins(buf, off, w - 2, swap) > 0:
            # подтверждаем следующей строкой: одиночный выброс не считается
            ny = min(y + coarse, h - 1)
            if shifted_wins(buf, ny * w * 2, w - 2, swap) > 0:
                start = max(0, y - coarse)
                for back in range(start, y + 1):
                    if shifted_wins(buf, back * w * 2, w - 2, swap) > 0:
                        return back, (median(base_rows) if base_rows else 0.0)
                return y, (median(base_rows) if base_rows else 0.0)
        base_rows.append(rough_at(buf, off, w, swap))
        y += coarse
    return None, (median(base_rows) if base_rows else 0.0)


def find_k(buf, w, lo, hi, swap=False, fine=24):
    """
    Точное смещение потерянного байта: наименьшее НЕЧЁТНОЕ p, с которого
    сдвинутое чтение начинает выигрывать.

    Сначала деление пополам широким окном в строку — оно устойчиво, но у
    самой границы размывается. Потом короткий добор мелким окном, чтобы
    попасть в байт, а не в его окрестность: лишние 100 байт — это полоска
    неверных пикселей, которая никуда не девается и раздувает JPEG.
    """
    lo |= 1
    hi |= 1
    if hi <= lo or hi + w * 2 + 2 > len(buf):
        hi = min(hi, len(buf) - w * 2 - 4) | 1
    if hi <= lo:
        return None
    # На НЕЧЁТНЫХ смещениях сравнение переворачивается: чтение «с p» и есть
    # исправленное, а «с p+1» — испорченное. Поэтому здесь ждём знак минус.
    if shifted_wins(buf, hi, w, swap, margin=1.0) >= 0:
        return None                       # выше по кадру чище не становится

    a, b = lo, hi
    while a + 2 < b:
        m = ((a + b) // 2) | 1
        if m <= a:
            break
        if shifted_wins(buf, m, w, swap, margin=1.0) < 0:
            b = m
        else:
            a = m + 2

    start = max(lo, b - fine * 8) | 1
    p = start
    while p <= b:
        if shifted_wins(buf, p, fine, swap, margin=1.0) < 0:
            return p
        p += 2
    return b


def insert_byte(buf, p, filler=None):
    """
    Вставляет байт на позицию p, сдвигая хвост вправо. Последний байт кадра
    выпадает — он возвращается, и этого достаточно для ТОЧНОГО отката. Копия
    кадра в 84 КБ не нужна: операция обратима одним байтом.
    """
    lost = buf[-1]
    if filler is None:
        filler = buf[p] if p < len(buf) else 0
    buf[p + 1:] = buf[p:-1]
    buf[p] = filler
    return lost


def undo_insert(buf, p, lost):
    buf[p:-1] = buf[p + 1:]
    buf[-1] = lost


# -------------------------------------------------------------- починка

def repair(buf, w, h, swap=False, max_passes=8):
    """
    Чинит кадр на месте. Возвращает отчёт.

    Вся мера порчи — число строк, которые уверенно читаются со сдвигом
    (shift_votes). Вставка байта принимается, только если это число СТАЛО
    МЕНЬШЕ, и отвергается иначе. Критерий структурный: он считает не «сколько
    шершавости», а «сколько строк лежит не на своей сетке», поэтому не зависит
    ни от сюжета, ни от освещения, ни от абсолютных порогов.

    Чем это отличается от двух испорченных попыток 25.09:
      версия 1 — абсолютный порог, срабатывал на контрастных сюжетах;
      версия 2 — проба по четырём строкам и выборка каждой восьмой, порча
                 пряталась между замерами;
      здесь   — все строки, сравнение двух чтений одного участка, точный
                откат одним байтом при любой неудаче.
    """
    rep = {"passes": [], "ok": False, "base": 0.0, "votes0": 0, "votes": 0,
           "before": 0.0, "after": 0.0, "clean": False}

    rows = row_roughness(buf, w, h, swap)
    rep["before"] = median(rows)
    rep["votes0"] = rep["votes"] = shift_votes(buf, w, h, swap)
    r, base = find_transition_row(buf, w, h, swap)
    rep["base"] = base
    if r is None or rep["votes0"] == 0:
        rep["clean"] = rep["ok"] = True
        rep["after"] = rep["before"]
        return rep

    for _ in range(max_passes):
        r, _ = find_transition_row(buf, w, h, swap)
        if r is None:
            break
        lo = max(0, (r - 2) * w * 2)
        hi = min(len(buf) - w * 2 - 4, (r + 3) * w * 2)
        k = find_k(buf, w, lo, hi, swap)
        if k is None:
            rep["passes"].append({"row": r, "k": None, "why": "место не найдено"})
            break

        before_votes = rep["votes"]
        before_rough = median(row_roughness(buf, w, h, swap))
        lost = insert_byte(buf, k)
        after_votes = shift_votes(buf, w, h, swap)
        after_rough = median(row_roughness(buf, w, h, swap))

        # Два условия, оба относительные: съехавших строк стало меньше И кадр
        # в целом не стал грубее. Второе страхует от «починки», которая
        # переставляет порчу с места на место.
        if after_votes >= before_votes or after_rough > before_rough * 1.1 + 0.5:
            undo_insert(buf, k, lost)
            rep["passes"].append({"row": r, "k": k,
                                  "why": "откат: строк со сдвигом %d -> %d, шершавость %.2f -> %.2f"
                                         % (before_votes, after_votes, before_rough, after_rough)})
            break
        rep["votes"] = after_votes
        rep["passes"].append({"row": r, "k": k,
                              "why": "вставка: строк со сдвигом %d -> %d"
                                     % (before_votes, after_votes)})
        if after_votes == 0:
            break

    rep["after"] = median(row_roughness(buf, w, h, swap))
    rep["votes"] = shift_votes(buf, w, h, swap)
    rep["ok"] = (rep["votes"] == 0)
    return rep


# ------------------------------------------------------------------ отчёт

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="BMP-кадры; по умолчанию все из tools/logs")
    ap.add_argument("--save", action="store_true", help="сохранить починенные кадры")
    ap.add_argument("--swap", action="store_true", help="младший байт первым")
    ap.add_argument("--passes", type=int, default=8, help="сколько вставок пробовать")
    args = ap.parse_args()

    files = args.files or sorted(glob.glob(os.path.join(LOGS, "raw_*.bmp")))
    files = [f for f in files if "_fixed" not in f]
    if not files:
        print("кадров не найдено")
        return

    print("%-26s %9s %7s %7s %9s  %s" %
          ("кадр", "строк_сдв", "было", "стало", "вердикт", "что сделано"))
    print("-" * 104)

    n_clean = n_fixed = n_part = n_failed = 0
    for path in files:
        w, h, buf = load_bmp565(path, args.swap)
        rep = repair(buf, w, h, args.swap, max_passes=args.passes)

        if rep["clean"]:
            verdict, n_clean = "цел", n_clean + 1
        elif rep["ok"]:
            verdict, n_fixed = "ПОЧИНЕН", n_fixed + 1
        elif rep["votes"] < rep["votes0"]:
            verdict, n_part = "улучшен", n_part + 1
        else:
            verdict, n_failed = "не вышло", n_failed + 1

        what = "; ".join("строка %d, байт %s: %s"
                         % (q["row"], q["k"], q["why"]) for q in rep["passes"])
        print("%-26s %4d->%-4d %7.2f %7.2f %9s  %s" %
              (os.path.basename(path), rep["votes0"], rep["votes"],
               rep["before"], rep["after"], verdict, what or "-"))

        if args.save and not rep["clean"]:
            save_bmp565(path.replace(".bmp", "_fixed.bmp"), buf, w, h, args.swap)

    print("-" * 104)
    print("целых %d, починено %d, улучшено %d, не вышло %d, всего %d"
          % (n_clean, n_fixed, n_part, n_failed, len(files)))


if __name__ == "__main__":
    main()
