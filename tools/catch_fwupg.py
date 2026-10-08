#!/usr/bin/env python3
"""
Дождаться включения платы, поймать стартовое окно модуля и залить прошивку.

    python tools/catch_fwupg.py --serial 20:6E:F1:A7:D4:28 \
        --file SDK/builds/APP_..._p2pdest.bin

ЗАЧЕМ ОТДЕЛЬНЫЙ ИНСТРУМЕНТ

Прошивка модуля заливается только в стартовое окно: после
UART_P2P_START_DELAY_MS (30 с) прозрачный режим забирает UART, и AT умирает до
следующего цикла питания. Окно одно, и промахнуться легко:

    рано  — порт ещё не появился, скрипт падает;
    поздно— окно закрылось, AT+NOP2P уже некому принять.

Ручной запуск после "включил" промахивается почти всегда: пока человек
переключится в терминал, из тридцати секунд остаётся десять, а на заливку
нужно больше минуты.

Поэтому здесь один процесс, который делает всё сам:

    1. ждёт появления порта ПО СЕРИЙНОМУ НОМЕРУ (имя COM между
       переподключениями меняется, серийный — нет);
    2. сразу начинает слать AT+NOP2P и ждёт OK — это отменяет запуск
       прозрачного режима НАСОВСЕМ до следующей перезагрузки, после чего
       спешить уже некуда;
    3. только тогда запускает tools/fwupg.py, который сам проверит
       контрольную сумму образа перед записью.

ЧТО ДЕЛАТЬ ЧЕЛОВЕКУ: запустить этот скрипт, потом снять питание с платы и
включить. Всё остальное произойдёт само.

ПРЕДУСЛОВИЕ: в ESP32 залит мост (examples/HalowPassthrough). Обычный скетч не
годится — он занимает UART модуля своим потоком.
"""

import argparse
import os
import subprocess
import sys
import time


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


def find_port(serial_no):
    """Найти порт по серийному номеру. Возвращает имя или None."""
    import serial.tools.list_ports as lp
    want = serial_no.lower().replace(":", "").replace("-", "")
    for p in lp.comports():
        hw = (p.hwid or "").lower().replace(":", "").replace("-", "")
        if want and want in hw:
            return p.device
    return None


def latch_at(port, deadline):
    """Слать AT+NOP2P, пока модуль не ответит OK. Возвращает True/False.

    Порт открываем и закрываем на каждой попытке: сразу после включения он
    может ещё перечисляться, и первое открытие нередко падает.
    """
    import serial
    tries = 0
    while time.time() < deadline:
        tries += 1
        try:
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = 115200
            ser.timeout = 0.4
            ser.write_timeout = 3
            ser.dtr = False
            ser.rts = False
            ser.open()
        except Exception:
            time.sleep(0.2)
            continue
        try:
            ser.reset_input_buffer()
            ser.write(b"AT+NOP2P\r\n")
            ser.flush()
            time.sleep(0.25)
            if b"OK" in ser.read(4096):
                print("  AT+NOP2P принят с %d-й попытки, AT-режим закреплён" % tries)
                return True
        except Exception:
            pass
        finally:
            try:
                ser.close()
            except Exception:
                pass
        time.sleep(0.1)
    print("  AT+NOP2P без ответа за отведённое время")
    return False


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--serial", required=True,
                   help="серийный номер платы, например 20:6E:F1:A7:D4:28")
    p.add_argument("--file", required=True, help="APP-образ для модуля")
    p.add_argument("--wait", type=float, default=600,
                   help="сколько секунд ждать включения платы")
    p.add_argument("--window", type=float, default=25,
                   help="сколько секунд ловить стартовое окно после появления порта")
    args = p.parse_args()

    if not os.path.exists(args.file):
        print("нет файла: %s" % args.file)
        return 2

    print("Жду плату (серийный %s)." % args.serial)
    print("СНИМИТЕ ПИТАНИЕ С ПЛАТЫ И ВКЛЮЧИТЕ — дальше всё само.")
    print("")

    # Если плата сейчас подключена, сначала дожидаемся её ИСЧЕЗНОВЕНИЯ: иначе
    # вцепимся в уже работающую, у которой окно давно закрыто.
    if find_port(args.serial):
        print("плата сейчас на связи, жду снятия питания...")
        end = time.time() + args.wait
        while time.time() < end and find_port(args.serial):
            time.sleep(0.1)
        if find_port(args.serial):
            print("питание так и не сняли")
            return 2
        print("  питание снято")

    end = time.time() + args.wait
    port = None
    while time.time() < end:
        port = find_port(args.serial)
        if port:
            break
        time.sleep(0.1)
    if not port:
        print("плата не появилась")
        return 2
    print("  плата на %s, ловлю стартовое окно" % port)

    if not latch_at(port, time.time() + args.window):
        print("")
        print("Окно упущено. Снимите питание и запустите снова.")
        return 2

    print("")
    print("Запускаю заливку.")
    print("")
    here = os.path.dirname(os.path.abspath(__file__))
    cmd = [sys.executable, os.path.join(here, "fwupg.py"),
           "--port", port, "--file", args.file, "--yes", "--serial", args.serial]
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
