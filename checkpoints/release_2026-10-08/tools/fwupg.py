#!/usr/bin/env python3
"""
Перепрошивка модуля TX-AH по AT+FWUPG + XMODEM через сервисный мост.

    python tools/fwupg.py --port COM7 \
        --file SDK/builds/APP_2.4.1.3-43933_2026-08-25_step3-230400-delay30s-nonetlog.bin --yes

ЧТО ЭТО ДЕЛАЕТ И ЧЕМ РИСКУЕТ

Заливает прошивку в МОДУЛЬ (не в ESP32). Модуль держит два слота и пишет в
неактивный, поэтому неудачная заливка обычно не смертельна: при следующей
загрузке поднимется прежняя. Но если процесс оборвётся в неудачный момент,
восстановление — это либо аппаратный debug-режим модуля, либо демонтаж
флеш-чипа (docs/Firmware_burn_1.md, _2.md). Поэтому --yes обязателен.

ПРЕДУСЛОВИЯ, без них не начинать:

1. В ESP32 этой платы залит мост (examples/HalowPassthrough). Обычный скетч
   не годится: он занимает UART модуля своим потоком.
2. Плата ОБЕСТОЧЕНА и включена заново непосредственно перед заливкой.
   Нужно, чтобы модуль загрузился и мост успел послать AT+NOP2P в его
   стартовое окно — иначе прозрачный режим заберёт UART и AT умрёт.
3. Шить только APP.bin (с заголовком). Не txw8301.bin и не param.bin —
   в параметрах лежат MAC, калибровка и роль, они уникальны для чипа.

ПРОТОКОЛ

AT+FWUPG переводит модуль в приём XMODEM: он начинает слать 'C', что означает
XMODEM с CRC16 (а не с однобайтовой контрольной суммой). Дальше блоки по 128
байт: SOH, номер, его дополнение, данные, CRC16. На каждый блок ждём ACK,
на NAK повторяем. В конце EOT.
"""

import argparse
import hashlib
import os
import struct
import sys
import time

SOH = 0x01
EOT = 0x04
ACK = 0x06
NAK = 0x15
CAN = 0x18
CRC_REQ = ord("C")

BLOCK = 128


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


def check_image_crc(data, force):
    """Сверить контрольную сумму образа ДО заливки.

    05.09, ценой окирпиченного модуля. В заголовке APP-образа лежит CRC тела:
    поле +0x14, младшие 16 бит, CRC16-MODBUS (отражённый, полином 0xA001,
    начальное 0xFFFF) по телу со смещения 0x2000 до конца файла. Алгоритм
    восстановлен перебором и проверен на всех тринадцати заводских сборках в
    SDK/builds.

    Что бывает, если не сверить. Загрузчик отвергает образ с неверной суммой,
    а AT+FWUPG к этому моменту УЖЕ снял метку годности со старого слота —
    значит запускать становится нечего, и модуль не поднимается вовсе. Ровно
    так 04.09 был потерян модуль камеры: он молчал на AT, не выходил в эфир, и
    двое суток это выглядело как содержательный отказ связи.

    Поэтому проверка здесь, а не в том инструменте, который образ готовит:
    портит железо именно заливка, ей и отвечать.
    """
    if len(data) < 0x2000 or data[:4] != bytes.fromhex("695a001c"):
        print("")
        print("ОТКАЗ: заголовок не 69 5a 00 1c — это не APP-образ.")
        return False

    crc = 0xFFFF
    for b in data[0x2000:]:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    want = struct.unpack_from("<I", data, 0x14)[0] & 0xFFFF

    if crc == want:
        print("CRC:    %04x — сходится" % crc)
        return True

    print("")
    print("ОТКАЗ: CRC тела не сходится — посчитано %04x, в заголовке %04x."
          % (crc, want))
    print("Загрузчик такой образ не примет, а метка старого слота к тому")
    print("моменту уже снята — модуль останется без рабочей прошивки и")
    print("поднимется только программатором.")
    print("Если образ правили вручную, пересчитайте сумму:")
    print("  python tools/p2p_dest.py set ... (он это делает сам)")
    if force:
        print("")
        print("--force-badcrc задан: продолжаю, риск на вас.")
        return True
    return False


def crc16_xmodem(data):
    """CRC16-CCITT с нулевым начальным значением — тот вариант, что требует XMODEM.

    Отличается от halow_crc16 в halow_stream.h начальным значением: там 0xFFFF,
    здесь 0x0000. Полином тот же, 0x1021.
    """
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def open_serial_quiet(port, baud=115200, timeout=1.0):
    """Открыть порт, не дёргая DTR/RTS: иначе плата перезагрузится и мы потеряем
    то самое стартовое окно, ради которого её только что включили."""
    import serial
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = timeout
    ser.write_timeout = 10
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser


def reopen(args, old_port):
    """08.10: дождаться возвращения порта после обрыва USB и открыть его тихо."""
    end = time.time() + args.reconnect_s
    while time.time() < end:
        port = old_port
        if args.serial:
            import serial.tools.list_ports as lp
            want = args.serial.lower().replace(":", "")
            port = None
            for pp in lp.comports():
                if want in (pp.hwid or "").lower().replace(":", ""):
                    port = pp.device
        if port:
            try:
                s = open_serial_quiet(port)
                s.reset_input_buffer()
                return s
            except Exception:
                pass
        time.sleep(0.3)
    return None


def wait_for(ser, wanted, seconds, label):
    """Ждать один из байтов wanted. Возвращает найденный байт или None."""
    end = time.time() + seconds
    seen = b""
    while time.time() < end:
        c = ser.read(1)
        if not c:
            continue
        seen += c
        if c[0] in wanted:
            return c[0]
        if c[0] == CAN:
            print("  модуль прислал CAN — отказ")
            return None
    if seen:
        txt = seen.decode("utf-8", "ignore").strip()
        if txt:
            print("  вместо %s пришло: %r" % (label, txt[-200:]))
    return None


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--yes", action="store_true",
                   help="подтверждение: пишем в модуль, не в ESP32")
    p.add_argument("--force-badcrc", action="store_true",
                   help="залить образ с несходящейся CRC (окирпичит модуль)")
    p.add_argument("--nop2p-tries", type=int, default=12)
    p.add_argument("--block-timeout", type=float, default=5.0)
    p.add_argument("--retries", type=int, default=10)
    p.add_argument("--serial", default="",
                   help="08.10: серийный номер платы — после обрыва USB искать порт по нему "
                        "и продолжать с того же блока (модуль при этом блок ждёт)")
    p.add_argument("--reconnect-s", type=float, default=30.0,
                   help="сколько ждать возвращения порта после обрыва USB")
    args = p.parse_args()

    if not os.path.exists(args.file):
        print("нет файла: %s" % args.file)
        return 2
    data = open(args.file, "rb").read()
    md5 = hashlib.md5(data).hexdigest()
    base = os.path.basename(args.file)

    print("файл:   %s" % base)
    print("размер: %d байт, %d блоков по %d" % (len(data), (len(data) + BLOCK - 1) // BLOCK, BLOCK))
    print("md5:    %s" % md5)
    if "param" in base.lower() or "txw8301" in base.lower():
        print("")
        print("ОТКАЗ: имя файла похоже на param.bin или txw8301.bin.")
        print("Шить можно только APP.bin — в остальных нет заголовка либо лежат")
        print("MAC, калибровка и роль, уникальные для этого чипа.")
        return 2

    if not check_image_crc(data, args.force_badcrc):
        return 2
    if not args.yes:
        print("")
        print("Это запись прошивки в МОДУЛЬ. Плата должна быть только что")
        print("включена, и в ESP32 должен быть залит мост HalowPassthrough.")
        print("Подтвердите ключом --yes.")
        return 1

    try:
        import serial  # noqa: F401
    except ImportError:
        print("нужен pyserial: pip install pyserial")
        return 2

    ser = open_serial_quiet(args.port)
    try:
        # Закрепляем AT-режим: если прошивка с прозрачным режимом, окно
        # короткое, и без этого UART уйдёт модулю.
        print("")
        print("закрепляю AT-режим...")
        latched = False
        for _ in range(args.nop2p_tries):
            ser.write(b"AT+NOP2P\r\n")
            ser.flush()
            time.sleep(0.3)
            if b"OK" in ser.read(4096):
                latched = True
                break
        print("  AT+NOP2P: %s" % ("принят" if latched else
                                  "без ответа (прошивка без прозрачного режима — норма)"))

        ser.reset_input_buffer()
        ser.write(b"AT+VERSION\r\n")
        ser.flush()
        time.sleep(0.5)
        ver = ser.read(4096).decode("utf-8", "ignore").strip()
        if "VERSION" not in ver:
            print("")
            print("ОТКАЗ: модуль не отвечает на AT. Заливку начинать нельзя.")
            print("Проверьте, что залит мост и что плату только что включили.")
            return 2
        print("  модуль: %s" % ver.replace("\r\n", " "))

        print("")
        print("AT+FWUPG, жду готовности приёмника...")
        ser.reset_input_buffer()
        ser.write(b"AT+FWUPG\r\n")
        ser.flush()
        if wait_for(ser, (CRC_REQ,), 20.0, "'C'") is None:
            print("ОТКАЗ: модуль не перешёл в режим XMODEM.")
            return 2
        print("  готов, пошла передача")

        total = (len(data) + BLOCK - 1) // BLOCK
        t0 = time.time()
        reconnects = 0
        for i in range(total):
            chunk = data[i * BLOCK:(i + 1) * BLOCK]
            if len(chunk) < BLOCK:
                chunk = chunk + b"\x1a" * (BLOCK - len(chunk))   # добивка CTRL-Z
            num = (i + 1) & 0xFF
            crc = crc16_xmodem(chunk)
            frame = bytes([SOH, num, 0xFF - num]) + chunk + bytes([crc >> 8, crc & 0xFF])

            for attempt in range(args.retries):
                try:
                    ser.write(frame)
                    ser.flush()
                    r = wait_for(ser, (ACK, NAK), args.block_timeout, "ACK")
                except Exception as e:
                    # 08.10: USB камеры рвётся на секунду-другую, питание при этом держится —
                    # ESP с мостом и модуль живы, модуль ждёт этот же блок. Переоткрыть порт
                    # и послать блок снова (повтор принятого блока XMODEM подтверждает).
                    print("")
                    print("  блок %d/%d: обрыв USB (%s) — жду порт" % (i + 1, total, type(e).__name__))
                    sys.stdout.flush()
                    try:
                        ser.close()
                    except Exception:
                        pass
                    ser = reopen(args, ser.port)
                    if ser is None:
                        print("ОТКАЗ: порт не вернулся за %.0f с." % args.reconnect_s)
                        print("Модуль пишет в НЕАКТИВНЫЙ слот — прежняя прошивка должна подняться.")
                        return 2
                    print("  порт вернулся (%s) — повторяю блок" % ser.port)
                    reconnects += 1
                    continue
                if r == ACK:
                    break
                if r is None:
                    print("")
                    print("ОТКАЗ: блок %d/%d остался без ответа." % (i + 1, total))
                    print("Модуль пишет в НЕАКТИВНЫЙ слот, поэтому при следующей")
                    print("загрузке должна подняться прежняя прошивка. Обесточьте")
                    print("плату и проверьте AT+VERSION.")
                    return 2
            else:
                print("")
                print("ОТКАЗ: блок %d/%d не принят за %d попыток." % (i + 1, total, args.retries))
                return 2

            if (i + 1) % 200 == 0 or i + 1 == total:
                pct = 100.0 * (i + 1) / total
                print("  %5d/%d  %5.1f%%  %4.0f с" % (i + 1, total, pct, time.time() - t0))
                sys.stdout.flush()

        ser.write(bytes([EOT]))
        ser.flush()
        if wait_for(ser, (ACK,), 20.0, "ACK на EOT") is None:
            print("")
            print("ВНИМАНИЕ: EOT остался без подтверждения. Данные, скорее всего,")
            print("записаны, но проверьте AT+VERSION после перезагрузки.")
            return 2

        print("")
        print("Передано за %.0f с (обрывов USB пережито: %d). Ответ модуля:"
              % (time.time() - t0, reconnects))
        time.sleep(2.0)
        tail = ser.read(8192).decode("utf-8", "ignore").strip()
        for line in tail.split("\n"):
            if line.strip():
                print("  " + line.strip())
        print("")
        print("Теперь ОБЕСТОЧЬТЕ плату и включите заново, затем проверьте:")
        print("  python tools/halow_at.py send --port %s \"AT+VERSION\" \"AT+SYSCFG\"" % args.port)
        print("В AT+SYSCFG сверьте build time с датой файла — так видно, какая")
        print("сборка реально поднялась.")
        return 0
    finally:
        ser.close()


if __name__ == "__main__":
    sys.exit(main())
