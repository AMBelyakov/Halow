#!/usr/bin/env python3
"""
Дождаться появления платы и НЕМЕДЛЕННО залить прошивку.

    python tools/wait_flash.py --serial 20:6E:F1:A7:D4:28 --file .pio/build/T-Halow/firmware.bin

Зачем отдельный инструмент. USB этих плат отказывает под нагрузкой: порт
перестаёт принимать запись, лечится только снятием питания, и после включения
есть примерно одна попытка, пока тракт снова не залип. Любое лишнее действие
между появлением порта и заливкой — проверка списка портов, ещё один запуск
интерпретатора — это окно съедает. 01.09 так было потеряно четыре попытки
подряд.

Поэтому здесь один процесс: он опрашивает список портов каждые 100 мс, находит
плату ПО СЕРИЙНОМУ НОМЕРУ (имя COM-порта между переподключениями меняется) и
сразу запускает esptool, не возвращая управление.

Заливается только образ приложения по 0x10000: загрузчик и таблица разделов
давно на месте и не меняются.

Про stub-загрузчик, 25.09. Раньше здесь был жёсткий --no-stub: штатный
upload падал именно на загрузке stub. Но падал он потому, что USB был
занят работающим скетчем и видеопотоком. Если скетча нет (плата с стёртым
приложением или только что включённая), stub грузится нормально и даёт
решающее преимущество в СКОРОСТИ.

А скорость здесь решает исход. USB этих плат отваливается от шины примерно
через полминуты непрерывной записи — доходило до 6%, до 67%, и всякий раз
обрыв. С --no-stub на 115200 полная запись идёт около минуты и НЕ УСПЕВАЕТ.
Со stub на 921600 та же запись занимает 2 секунды и проскакивает окно целиком.

Поэтому порядок такой: сначала --fast (stub, 921600), и только если stub
не грузится — медленный путь.
"""

import argparse
import os
import subprocess
import sys
import time

ESPTOOL = r"C:/.platformio/packages/tool-esptoolpy@1.40501.0/esptool.py"
PYTHON = r"C:/.platformio/penv/Scripts/python.exe"


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


def find_port(serial_tag):
    import serial.tools.list_ports as lp
    for p in lp.comports():
        if serial_tag.lower() in (p.hwid or "").lower():
            return p.device
    return None


# ОТЛИЧИТЬ РЕЖИМ ПЗУ ПО VID:PID НЕЛЬЗЯ. 15.09 была попытка ловить плату в
# режиме загрузчика по паре 303A:1001 — оказалось, что под этой же парой она
# видна и с работающим скетчем (USB отдаёт один и тот же блок чипа). Ловилка
# хватала обычную работающую плату, слала esptool с --before no_reset и
# получала "No serial data received". Отличать режимы приходится по поведению
# порта, а не по его идентификаторам.


def wait_gone(serial_tag, seconds):
    """Дождаться, пока плата ПРОПАДЁТ из списка портов (сняли питание)."""
    end = time.time() + seconds
    while time.time() < end:
        if not find_port(serial_tag):
            return True
        time.sleep(0.1)
    return False


def openable(port):
    """Порт есть в списке — ещё не значит, что он готов.

    01.09: список показывал COM6, а esptool через долю секунды получал
    "порт не существует". Windows держит запись об отключённой плате и
    регистрирует новую раньше, чем та готова. Поэтому единственная надёжная
    проверка — попробовать открыть по-настоящему.

    Открываем как всегда, не дёргая DTR/RTS: иначе сбросим плату и потеряем
    то самое окно, ради которого всё и затевалось.
    """
    try:
        import serial
        s = serial.Serial()
        s.port = port
        s.baudrate = 115200
        s.timeout = 0.2
        s.dtr = False
        s.rts = False
        s.open()
        s.close()
        return True
    except Exception:
        return False


def wait_ready(serial_tag, seconds):
    """Дождаться платы, которая действительно открывается."""
    end = time.time() + seconds
    while time.time() < end:
        port = find_port(serial_tag)
        if port and openable(port):
            return port
        time.sleep(0.1)
    return None


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serial", required=True,
                    help="серийный номер платы, например 20:6E:F1:A7:D4:28")
    ap.add_argument("--file", required=True)
    ap.add_argument("--addr", default="0x10000")
    ap.add_argument("--wait", type=float, default=180.0)
    ap.add_argument("--settle", type=float, default=1.0,
                    help="пауза после появления порта, чтобы он успел готовиться")
    ap.add_argument("--attempts", type=int, default=3,
                    help="сколько раз повторить заливку, если сорвалась")
    ap.add_argument("--fast", action="store_true",
                    help="со stub-загрузчиком и на 921600: запись за 2 с вместо минуты. "
                         "Главное лекарство от обрыва USB посреди записи: плата "
                         "отваливается примерно через полминуты, и быстрая запись просто "
                         "успевает до обрыва. Требует свободного USB: с работающим "
                         "скетчем и видеопотоком stub не грузится.")
    ap.add_argument("--baud", type=int, default=0,
                    help="скорость заливки; по умолчанию 921600 с --fast и 115200 без него")
    ap.add_argument("--reset", default="usb_reset",
                    choices=("usb_reset", "default_reset", "no_reset"),
                    help="как вводить плату в загрузчик. На этой плате "
                         "ARDUINO_USB_MODE=1, то есть USB поднимает встроенный "
                         "блок USB-Serial/JTAG, и для него нужен usb_reset. "
                         "default_reset дёргает DTR/RTS как у классического "
                         "переходника — на этом блоке срабатывает не всегда, "
                         "и тогда esptool не может даже отправить синхропакет: "
                         "приёмный буфер блока никто не разгребает, запись "
                         "упирается в Write timeout.")
    ap.add_argument("--cycle", action="store_true",
                    help="сначала дождаться СНЯТИЯ питания, и только потом "
                         "ловить плату. Без этого ловилка мгновенно хватает "
                         "уже работающую плату, у которой USB занят скетчем и "
                         "потоком видео, — оттуда и Write timeout. Ловить надо "
                         "ровно в момент включения, пока скетч ещё не "
                         "разогнался.")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print("нет файла: %s" % args.file)
        return 2

    if args.cycle and find_port(args.serial):
        print("плата на связи. СНИМИТЕ ПИТАНИЕ — жду...")
        sys.stdout.flush()
        if not wait_gone(args.serial, args.wait):
            print("питание так и не сняли")
            return 2
        print("  питание снято, теперь включайте")
        sys.stdout.flush()

    print("жду плату %s (до %.0f с)..." % (args.serial, args.wait))
    sys.stdout.flush()

    for attempt in range(1, args.attempts + 1):
        port = wait_ready(args.serial, args.wait)
        if not port:
            print("плата не появилась")
            return 2
        time.sleep(args.settle)
        if not openable(port):
            print("порт %s перестал открываться, жду заново" % port)
            continue
        print("готова: %s — заливаю (попытка %d)" % (port, attempt))
        sys.stdout.flush()
        baud = args.baud or (921600 if args.fast else 115200)
        cmd = [PYTHON, ESPTOOL, "--chip", "esp32s3", "--port", port,
               "--baud", str(baud)]
        if not args.fast:
            cmd.append("--no-stub")
        cmd += ["--before", args.reset, "--after", "hard_reset",
                "write_flash", "-z", args.addr, args.file]
        if subprocess.call(cmd) == 0:
            print("")
            print("залито с попытки %d" % attempt)
            return 0
        print("")
        print("попытка %d не удалась" % attempt)
    print("не удалось. Обесточьте плату и запустите снова с --cycle.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
