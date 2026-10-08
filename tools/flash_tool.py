#!/usr/bin/env python3
"""
flash_tool.py — заливка прошивки в SPI NOR флеш через ESP32.

Пара к tools/SpiFlashProgrammer/SpiFlashProgrammer.ino. Нужен для
восстановления STA-модуля T-Halow после неудачной прошивки: модуль ушёл в
циклический ребут и по UART недоступен, поэтому флеш вынимается из кроватки
и прошивается снаружи.

Использование:

    # 1. Проверить связь и опознать чип (ничего не пишет)
    python flash_tool.py --port COM6 id

    # 2. Снять дамп текущего содержимого ПЕРЕД тем как что-либо стирать
    python flash_tool.py --port COM6 read backup.bin --size 1048576

    # 3. Прошить и проверить
    python flash_tool.py --port COM6 write ../firmware/version1/huge-ic-ah_v1.6.4.3-28977_2024.5.29_TAIXIN-WNB.bin

    # 4. Отдельно сверить, если нужно
    python flash_tool.py --port COM6 verify <тот же файл>

Команда write сама стирает, пишет и верифицирует. Без успешной верификации
она завершается с ненулевым кодом — молча "залилось вроде" не будет.
"""

import argparse
import sys
import time
import zlib

try:
    import serial
except ImportError:
    sys.exit("Нужен pyserial:  pip install pyserial")

CHUNK = 4096
SECTOR = 4096          # минимальная единица стирания у W25Q
# Известные ID производителей — только чтобы вывести человекочитаемое имя.
# На работу не влияет: команды SPI NOR у всех перечисленных одинаковые.
MFR = {0xEF: "Winbond", 0xC2: "Macronix", 0xC8: "GigaDevice",
       0x20: "Micron/ST", 0x1C: "EON", 0xBF: "SST", 0x9D: "ISSI"}


class Programmer:
    def __init__(self, port, baud=115200, timeout=5):
        self.ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(2.0)              # ESP32-S3 перезагружается при открытии порта
        self.ser.reset_input_buffer()

    def _cmd(self, text):
        self.ser.write((text + "\n").encode())
        self.ser.flush()

    def _line(self):
        ln = self.ser.readline().decode(errors="replace").strip()
        if not ln:
            raise RuntimeError("нет ответа от ESP32 (таймаут)")
        return ln

    def ping(self):
        # Скетч при старте печатает баннер — вычитываем всё лишнее
        self.ser.reset_input_buffer()
        self._cmd("PING")
        for _ in range(5):
            if self._line() == "OK":
                return True
        raise RuntimeError("ESP32 не отвечает на PING")

    def chip_id(self):
        self._cmd("ID")
        ln = self._line()
        if not ln.startswith("JEDEC"):
            raise RuntimeError(f"неожиданный ответ: {ln}")
        p = ln.split()
        mfr, typ, cap = int(p[1], 16), int(p[2], 16), int(p[3], 16)
        size = int(p[5])
        return mfr, typ, cap, size

    def erase_chip(self):
        """Полное стирание. НЕ используется обычной заливкой: на 4 МБ чипе
        прошивка занимает первые ~335 КБ, а дальше лежит параметрическая
        область с MAC и заводской калибровкой. Стереть её — значит потерять
        их безвозвратно."""
        self._cmd("ERASE")
        old = self.ser.timeout
        self.ser.timeout = 180
        try:
            ln = self._line()
        finally:
            self.ser.timeout = old
        if ln != "OK":
            raise RuntimeError(f"стирание не удалось: {ln}")

    def erase_sector(self, addr):
        self._cmd(f"SE {addr}")
        ln = self._line()
        if ln != "OK":
            raise RuntimeError(f"стирание сектора {addr} не удалось: {ln}")

    def write_chunk(self, addr, data):
        self._cmd(f"W {addr} {len(data)}")
        if self._line() != "RDY":
            raise RuntimeError("ESP32 не готов принимать данные")
        self.ser.write(data)
        self.ser.flush()
        ln = self._line()
        if not ln.startswith("OK"):
            raise RuntimeError(f"ошибка записи по адресу {addr}: {ln}")
        got = int(ln.split()[1], 16)
        want = zlib.crc32(data) & 0xFFFFFFFF
        if got != want:
            raise RuntimeError(
                f"CRC не сошлась по адресу {addr}: чип {got:08X}, ожидали {want:08X}")

    def read_chunk(self, addr, length):
        self._cmd(f"R {addr} {length}")
        ln = self._line()
        if not ln.startswith("DATA"):
            raise RuntimeError(f"неожиданный ответ: {ln}")
        n = int(ln.split()[1])
        buf = b""
        while len(buf) < n:
            part = self.ser.read(n - len(buf))
            if not part:
                raise RuntimeError("обрыв при чтении")
            buf += part
        return buf

    def close(self):
        self.ser.close()


def progress(done, total, label):
    pct = 100 * done // total if total else 100
    bar = "#" * (pct // 4) + "." * (25 - pct // 4)
    print(f"\r  {label} [{bar}] {pct:3d}%  {done}/{total}", end="", flush=True)


def do_id(pr):
    mfr, typ, cap, size = pr.chip_id()
    name = MFR.get(mfr, "неизвестный производитель")
    print(f"JEDEC ID : {mfr:02X} {typ:02X} {cap:02X}  ({name})")
    if size:
        print(f"Объём    : {size} байт ({size // 1024} КБ)")
    else:
        print("Объём    : не распознан — задайте --size вручную")
    if mfr in (0x00, 0xFF):
        print("\nВНИМАНИЕ: ID состоит из одних 00 или FF. Это почти всегда")
        print("значит, что чип не отвечает: проверьте питание 3.3 В, землю,")
        print("подтяжку /WP и /HOLD к 3.3 В и правильность CS/CLK/DI/DO.")
    return size


def do_read(pr, path, size):
    print(f"Читаю {size} байт в {path}")
    data = bytearray()
    while len(data) < size:
        n = min(CHUNK, size - len(data))
        data += pr.read_chunk(len(data), n)
        progress(len(data), size, "чтение")
    print()
    with open(path, "wb") as f:
        f.write(data)
    print(f"Сохранено: {path}")


def do_verify(pr, path, base=0):
    with open(path, "rb") as f:
        want = f.read()
    print(f"Сверяю {len(want)} байт с адреса 0x{base:06X}")
    for off in range(0, len(want), CHUNK):
        n = min(CHUNK, len(want) - off)
        got = pr.read_chunk(base + off, n)
        if got != want[off:off + n]:
            # находим точное место первого расхождения — полезнее, чем "не совпало"
            for i in range(n):
                if got[i] != want[off + i]:
                    print(f"\nРАСХОЖДЕНИЕ по адресу 0x{base + off + i:06X}: "
                          f"в чипе {got[i]:02X}, в файле {want[off + i]:02X}")
                    return False
        progress(off + n, len(want), "сверка")
    print("\nСовпадает полностью.")
    return True


def do_write(pr, path, base=0):
    with open(path, "rb") as f:
        data = f.read()
    end = base + len(data)
    print(f"Файл: {path} ({len(data)} байт)")
    print(f"Диапазон: 0x{base:06X}..0x{end:06X}")
    print("Всё, что за этим диапазоном (MAC, калибровка), не трогается.")

    # Стираем только сектора, попадающие в диапазон записи.
    first = base // SECTOR
    last = (end + SECTOR - 1) // SECTOR
    print(f"Стираю {last - first} секторов по 4 КБ...")
    for i, s in enumerate(range(first, last)):
        pr.erase_sector(s * SECTOR)
        progress(i + 1, last - first, "стирание")
    print()

    for off in range(0, len(data), CHUNK):
        pr.write_chunk(base + off, data[off:off + CHUNK])
        progress(off + len(data[off:off + CHUNK]), len(data), "запись")
    print()

    return do_verify(pr, path, base)


def main():
    ap = argparse.ArgumentParser(description="Прошивка SPI NOR через ESP32")
    ap.add_argument("--port", required=True, help="COM-порт ESP32, например COM6")
    ap.add_argument("--baud", type=int, default=115200)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("id", help="опознать чип, ничего не менять")

    p_r = sub.add_parser("read", help="снять дамп в файл")
    p_r.add_argument("file")
    p_r.add_argument("--size", type=int, default=0,
                     help="сколько байт читать (по умолчанию — весь объём чипа)")

    p_w = sub.add_parser("write", help="записать и проверить (посекторно)")
    p_w.add_argument("file")
    p_w.add_argument("--at", type=lambda s: int(s, 0), default=0,
                     help="адрес записи, напр. 0x0 (по умолчанию 0)")

    p_v = sub.add_parser("verify", help="сверить содержимое с файлом")
    p_v.add_argument("file")
    p_v.add_argument("--at", type=lambda s: int(s, 0), default=0)

    args = ap.parse_args()

    pr = Programmer(args.port, args.baud)
    try:
        pr.ping()
        size = do_id(pr)
        print()

        if args.cmd == "id":
            return 0

        if args.cmd == "read":
            n = args.size or size
            if not n:
                sys.exit("Объём чипа не определён — укажите --size")
            do_read(pr, args.file, n)
            return 0

        if args.cmd == "verify":
            return 0 if do_verify(pr, args.file, args.at) else 1

        if args.cmd == "write":
            return 0 if do_write(pr, args.file, args.at) else 1

    finally:
        pr.close()


if __name__ == "__main__":
    sys.exit(main())
