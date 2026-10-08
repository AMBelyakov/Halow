# -*- coding: utf-8 -*-
"""Заливка образа приложения КУСКАМИ с продолжением после срыва (07.10).

07.10 вечером USB камеры держался секунду-полторы записи, а образ (~400 КБ, сжатый
~230 КБ) пишется 2,2 с — почти каждая попытка рвалась на 6–60 % и начиналась с нуля.
Здесь образ режется на куски по границе сектора (4 КБ), каждый кусок esptool пишет и
проверяет хешем отдельно («Hash of data verified» на файл). Срыв — плату передёрнуть с
BOOT, и заливка продолжается с первого непроверенного куска. Куски одного образа, так что
половина старого приложения в промежутке никому не мешает: плата в загрузчике.

    python -u tools/flash_parts.py --serial 20:6E:F1:A7:D4:28 --file образ.bin

Ожидание платы — как в wait_flash.py --cycle: сначала снять питание, потом с BOOT воткнуть.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wait_flash as wf  # noqa: E402  (find_port, wait_gone, wait_ready, ESPTOOL, PYTHON)

SECTOR = 4096


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--addr", type=lambda v: int(v, 0), default=0x10000)
    ap.add_argument("--part-kb", type=int, default=64,
                    help="размер куска до сжатия, КБ (кратно 4); 64 КБ ≈ 0,3 с записи")
    ap.add_argument("--rounds", type=int, default=20)
    ap.add_argument("--wait", type=float, default=1800.0)
    ap.add_argument("--settle", type=float, default=3.0)
    ap.add_argument("--skip", type=int, default=0,
                    help="столько первых кусков уже записано и проверено (продолжить)")
    args = ap.parse_args()

    data = open(args.file, "rb").read()
    step = max(SECTOR, (args.part_kb * 1024) // SECTOR * SECTOR)
    tmp = tempfile.mkdtemp(prefix="flash_parts_")
    parts = []
    for i, off in enumerate(range(0, len(data), step)):
        fn = os.path.join(tmp, "part%02d.bin" % i)
        open(fn, "wb").write(data[off:off + step])
        parts.append((args.addr + off, fn))
    done = min(args.skip, len(parts))
    print("образ %d байт, кусков %d по %d КБ" % (len(data), len(parts), step // 1024))

    for rnd in range(1, args.rounds + 1):
        if wf.find_port(args.serial):
            print("круг %d: плата на связи. СНИМИТЕ ПИТАНИЕ — жду..." % rnd)
            sys.stdout.flush()
            if not wf.wait_gone(args.serial, args.wait):
                print("питание так и не сняли")
                return 2
        print("  питание снято, теперь с BOOT включайте (осталось кусков %d из %d)"
              % (len(parts) - done, len(parts)))
        sys.stdout.flush()
        port = wf.wait_ready(args.serial, args.wait)
        if not port:
            print("плата не появилась")
            return 2
        time.sleep(args.settle)
        cmd = [wf.PYTHON, wf.ESPTOOL, "--chip", "esp32s3", "--port", port, "--baud", "921600",
               "--before", "no_reset", "--after", "hard_reset", "write_flash", "-z"]
        for a, fn in parts[done:]:
            cmd += ["0x%x" % a, fn]
        print("готова: %s — пишу куски %d..%d" % (port, done + 1, len(parts)))
        sys.stdout.flush()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        ok_now = 0
        tail = []
        for raw in p.stdout:
            line = raw.decode("utf-8", "replace").rstrip()
            tail.append(line)
            print(line)
            sys.stdout.flush()
            if "Hash of data verified" in line:
                ok_now += 1
        rc = p.wait()
        done += ok_now
        if not ok_now and "doesn't exist" in "".join(tail[-5:]):
            # Дребезг контакта при втыкании: порт мигнул. Если BOOT ещё держат, чип снова в
            # загрузчике — подождать порт и повторить сразу, без нового передёргивания.
            port2 = wf.wait_ready(args.serial, 6.0)
            if port2:
                print("порт мигнул — повторяю сразу на %s" % port2)
                time.sleep(1.0)
                cmd[cmd.index("--port") + 1] = port2
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                for raw in p.stdout:
                    line = raw.decode("utf-8", "replace").rstrip()
                    print(line)
                    sys.stdout.flush()
                    if "Hash of data verified" in line:
                        ok_now += 1
                rc = p.wait()
                done += ok_now
        print("круг %d: проверено кусков %d, всего %d из %d" % (rnd, ok_now, done, len(parts)))
        if done >= len(parts):
            print("залито: все %d кусков проверены хешем" % len(parts))
            return 0
        if rc == 0:
            print("esptool вышел без ошибки, но не все куски проверены — повторяю")
    print("не удалось за %d кругов" % args.rounds)
    return 1


if __name__ == "__main__":
    sys.exit(main())
