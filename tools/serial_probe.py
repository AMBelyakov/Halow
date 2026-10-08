#!/usr/bin/env python3
"""
Минимальный щуп COM-порта: читает байты и раз в секунду печатает, сколько
пришло. Больше ничего — ни разбора кадров, ни сборки JPEG, ни CSV, ни HTTP.

Зачем. В логах просмотрщика раз в минуту появляется провал на 3-4 секунды, а
следом пачка со скоростью ВЫШЕ пропускной способности провода. Значит данные
не теряются, а где-то копятся, и вопрос только в том, кто перестаёт читать.

    python tools/serial_probe.py COM7

Если провалы видны и здесь — виноват не наш разбор, а всё, что ниже: драйвер
COM-порта, USB или сам приёмник. Если провалов нет — виноват просмотрщик, и
чинить надо его.

Столбцы:
    t      секунд от старта
    КБ/с   принято за эту секунду
    всего  накопительно
    пауза  максимальный промежуток между чтениями внутри секунды, мс —
           показывает, читали ли мы порт ровно или замирали
"""

import sys
import time


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    port = sys.argv[1]
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200

    try:
        import serial
    except ImportError:
        print("нужен pyserial: pip install pyserial")
        return

    with serial.Serial(port, baud, timeout=0.05) as ser:
        # pyserial при открытии поднимает DTR/RTS, а на ESP32 они обычно ведут
        # на RESET/BOOT — плата зависнет в сбросе. Отпускаем сразу.
        ser.dtr = False
        ser.rts = False
        print("читаю %s, вывод раз в секунду, Ctrl+C для выхода" % port)

        t0 = time.time()
        tick = t0
        got = 0
        total = 0
        last_read = time.time()
        max_gap = 0.0

        try:
            while True:
                chunk = ser.read(8192)
                now = time.time()
                if chunk:
                    gap = now - last_read
                    if gap > max_gap:
                        max_gap = gap
                    last_read = now
                    got += len(chunk)
                    total += len(chunk)

                if now - tick >= 1.0:
                    print("t=%6.1f  %6.1f КБ/с  всего %8.1f КБ  пауза %5.0f мс"
                          % (now - t0, got / 1024.0 / (now - tick),
                             total / 1024.0, max_gap * 1000))
                    tick = now
                    got = 0
                    max_gap = 0.0
        except KeyboardInterrupt:
            dt = time.time() - t0
            print("\nитого %.1f КБ за %.1f с, в среднем %.1f КБ/с"
                  % (total / 1024.0, dt, total / 1024.0 / dt if dt else 0))


if __name__ == "__main__":
    main()
