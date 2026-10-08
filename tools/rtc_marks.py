#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Прочитать метки загрузки из RTC-памяти платы с камерой.

ЗАЧЕМ ЭТО НУЖНО
Скетч печатает лог в USB, но USB на этой плате — USB-Serial/JTAG, и запись в
него только кладёт байты в кольцо; выгребает их прерывание. Стоит чему-нибудь
надолго занять ядро — лог пропадает целиком, и плата выглядит мёртвой, хотя
работает. Ещё хуже, когда она перезагружается: последние строки не успевают
уйти, и причина остаётся неизвестной.

Поэтому скетч дублирует несколько чисел в RTC-память. Она переживает
перезагрузку (очищается только снятием питания) и читается программатором, то
есть не зависит ни от консоли, ни от того, жив ли скетч.

КАК ПОЛЬЗОВАТЬСЯ
Плата ведёт себя странно — запустить и посмотреть:

    python tools/rtc_marks.py            # порт по умолчанию COM6
    python tools/rtc_marks.py --port COM7

  загрузок сильно больше ожидаемого  -> плата перезагружается сама
  причина сброса PANIC/WDT/BROWNOUT  -> прямой ответ, отчего именно
  шаг меньше 8                       -> не дошла до основного цикла, место видно

ВАЖНО: чтение вводит плату в режим загрузчика и в конце сбрасывает её обратно
в приложение. Счётчик загрузок при этом вырастет на единицу — это нормально,
просто учитывайте.
"""
import argparse
import struct
import subprocess
import sys
import os

ESPTOOL = r"C:/.platformio/packages/tool-esptoolpy/esptool.py"
RTC_BASE = 0x50000000
RTC_LEN = 20

# Порядок полей — как они легли в память, см. nm firmware.elf | grep dbg_
FIELDS = ("maxstage", "reason", "boots", "stage", "magic")
MAGIC = 0x48414C4F  # "HALO"

REASONS = {
    0: "UNKNOWN — причина не определена",
    1: "POWERON — подано питание",
    2: "EXT — внешний сброс",
    3: "SW — программный перезапуск (в т.ч. заливка)",
    4: "PANIC — исключение, плата упала",
    5: "INT_WDT — сторож прерываний",
    6: "TASK_WDT — сторож задач: задача не отдавала ядро",
    7: "WDT — прочий сторожевой таймер",
    8: "DEEPSLEEP",
    9: "BROWNOUT — просадка питания",
    10: "SDIO",
    11: "USB",
    12: "JTAG",
}

STAGES = {
    1: "вошли в setup()",
    2: "Serial поднят",
    3: "задержка 2 с позади",
    4: "камера поднята",
    5: "память развязана (буфер в SRAM)",
    6: "конвейер создан",
    7: "стартовое окно настроено",
    8: "дошли до loop()",
    9: "окно закрылось, начали поток",
    10: "кадр ушёл целиком — всё работает",
}


def main():
    ap = argparse.ArgumentParser(description="Метки загрузки из RTC-памяти T-Halow")
    ap.add_argument("--port", default="COM6")
    ap.add_argument("--esptool", default=ESPTOOL)
    ap.add_argument("--keep-in-bootloader", action="store_true",
                    help="не сбрасывать плату в приложение после чтения")
    args = ap.parse_args()

    dump = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "rtc.bin")
    os.makedirs(os.path.dirname(dump), exist_ok=True)

    cmd = [sys.executable, args.esptool, "--chip", "esp32s3", "--port", args.port,
           "--before", "default_reset",
           "--after", "no_reset" if args.keep_in_bootloader else "hard_reset",
           "dump_mem", hex(RTC_BASE), str(RTC_LEN), dump]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        sys.stderr.write("\nНе удалось прочитать. Если порт занят — закройте монитор.\n")
        return 1

    vals = dict(zip(FIELDS, struct.unpack("<5I", open(dump, "rb").read(RTC_LEN))))

    if vals["magic"] != MAGIC:
        print("RTC-память пуста или очищена (плату обесточивали) — данных нет.")
        return 0

    print("загрузок с момента подачи питания : %d" % vals["boots"])
    print("шаг последнего запуска            : %d — %s"
          % (vals["stage"], STAGES.get(vals["stage"], "?")))
    print("самый дальний шаг за все запуски  : %d — %s"
          % (vals["maxstage"], STAGES.get(vals["maxstage"], "до loop() не доходила")))
    print("причина последнего сброса         : %d — %s"
          % (vals["reason"], REASONS.get(vals["reason"], "?")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
