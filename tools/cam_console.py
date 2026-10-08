#!/usr/bin/env python3
"""
Писать в файл всё, что печатает плата в USB-консоль, переживая её перезагрузки.

    python tools/cam_console.py --serial 20:6E:F1:A7:D4:28 --tag unicast

ЗАЧЕМ ОТДЕЛЬНЫЙ ИНСТРУМЕНТ

Обычный монитор порта (pio device monitor и любой терминал) умирает вместе с
портом: плата перезагрузилась — порт исчез — монитор отвалился, и остаток
прогона писать некому. А самое интересное на этих платах происходит как раз
вокруг перезагрузок: стартовое окно AT, ответ модуля на AT+P2PDEST, паника без
единой строки лога.

Поэтому здесь порт ищется ПО СЕРИЙНОМУ НОМЕРУ (имя COM между переподключениями
меняется, серийный — нет) и переоткрывается сам. В файл при этом ставятся
отметки, чтобы потом было видно, где кончился один запуск платы и начался
следующий:

    --- порт открыт ЧЧ:ММ:СС ---
    --- ПИТАНИЕ СНЯТО ЧЧ:ММ:СС ---

Без этих отметок склеенный лог читается неверно: две загрузки выглядят как
одна, и непонятно, к какой из них относится строка.

Файл пишется в tools/logs/cam_console_ГГГГММДД_ЧЧММСС_метка.txt и сбрасывается
на диск после каждой строки — если плата или компьютер зависнут, написанное
останется.
"""

import argparse
import io
import os
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


def find_port(serial_tag):
    import serial.tools.list_ports as lp
    for p in lp.comports():
        if serial_tag.lower() in (p.hwid or "").lower():
            return p.device
    return None


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serial", required=True,
                    help="серийный номер платы, например 20:6E:F1:A7:D4:28")
    ap.add_argument("--tag", default="run", help="метка в имени файла")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--minutes", type=float, default=0,
                    help="остановиться через столько минут (0 — без предела)")
    args = ap.parse_args()

    import serial

    here = os.path.dirname(os.path.abspath(__file__))
    logdir = os.path.join(here, "logs")
    if not os.path.isdir(logdir):
        os.makedirs(logdir)
    name = "cam_console_%s_%s.txt" % (time.strftime("%Y%m%d_%H%M%S"), args.tag)
    path = os.path.join(logdir, name)
    out = io.open(path, "w", encoding="utf-8", newline="\n")

    print("пишу в %s" % path)
    print("Ctrl+C — остановить")
    sys.stdout.flush()

    deadline = time.time() + args.minutes * 60 if args.minutes > 0 else None
    ser = None
    tail = ""

    def mark(text):
        out.write("--- %s %s ---\n" % (text, time.strftime("%H:%M:%S")))
        out.flush()

    try:
        while deadline is None or time.time() < deadline:
            if ser is None:
                port = find_port(args.serial)
                if not port:
                    time.sleep(0.2)
                    continue
                try:
                    ser = serial.Serial()
                    ser.port = port
                    ser.baudrate = args.baud
                    ser.timeout = 0.2
                    # Не трогаем DTR/RTS: на этих платах они заведены на сброс
                    # и режим загрузки, дёрнешь — перезагрузишь плату.
                    ser.dtr = False
                    ser.rts = False
                    ser.open()
                except Exception:
                    ser = None
                    time.sleep(0.3)
                    continue
                mark("порт открыт")
                continue

            try:
                chunk = ser.read(4096)
            except Exception:
                chunk = None

            if chunk is None:
                # Порт умер под нами — почти всегда это снятое питание.
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                mark("ПИТАНИЕ СНЯТО")
                continue

            if not chunk:
                if find_port(args.serial) is None:
                    try:
                        ser.close()
                    except Exception:
                        pass
                    ser = None
                    mark("ПИТАНИЕ СНЯТО")
                continue

            tail += chunk.decode("utf-8", "replace")
            while "\n" in tail:
                line, tail = tail.split("\n", 1)
                out.write(line.rstrip("\r") + "\n")
            out.flush()
    except KeyboardInterrupt:
        pass
    finally:
        if tail:
            out.write(tail + "\n")
        out.flush()
        out.close()
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
    print("")
    print("лог: %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
