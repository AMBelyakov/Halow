#!/usr/bin/env python3
"""
Полная перепрошивка одной платы T-Halow: мост в ESP32 -> прошивка модуля -> скетч.

    python tools/flash_chain.py --serial 9C:13:9E:B5:B3:C0 --name Б \
        --modfw SDK/builds/APP_..._ccasw.bin --app .pio/keep/HalowVideoP2P_AP_..._ccasw.bin

Каждый шаг ждёт, пока плату выдернут и воткнут обратно (по серийному номеру), и
перед этим пищит: три коротких — «передёрни плату». Шаги:
    1) tools/wait_flash.py --cycle  — мост HalowPassthrough в ESP32;
    2) tools/catch_fwupg.py         — прошивка модуля (fwupg.py сверяет CRC);
    3) tools/wait_flash.py --cycle  — рабочий скетч в ESP32.
После шага 3 плата в режиме загрузчика до следующего передёргивания.
--skip-mod — без шагов 1–2 (только скетч).
"""
import argparse
import subprocess
import sys
import time

PY = sys.executable
BRIDGE = ".pio/keep/HalowPassthrough.bin"


def beep(n=3):
    try:
        import winsound
        for _ in range(n):
            winsound.Beep(1400, 250)
            time.sleep(0.12)
    except Exception:
        print("\a", end="", flush=True)


def run(title, cmd):
    print("=== %s: %s" % (time.strftime("%H:%M:%S"), title), flush=True)
    beep()
    r = subprocess.run(cmd)
    ok = r.returncode == 0
    print("=== %s: %s — %s" % (time.strftime("%H:%M:%S"), title,
                                "ГОТОВО" if ok else "ОШИБКА %d" % r.returncode), flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serial", required=True)
    ap.add_argument("--name", default="?")
    ap.add_argument("--modfw")
    ap.add_argument("--app", required=True)
    ap.add_argument("--skip-mod", action="store_true")
    a = ap.parse_args()
    fl = [PY, "-u", "tools/wait_flash.py", "--serial", a.serial, "--fast", "--cycle",
          "--settle", "0.5", "--attempts", "5", "--wait", "1500"]
    n = a.name
    if not a.skip_mod:
        if not run("плата %s, шаг 1/3: мост в ESP32 — ПЕРЕДЁРНИ %s" % (n, n),
                   fl + ["--file", BRIDGE]):
            return 1
        if not run("плата %s, шаг 2/3: прошивка модуля — ПЕРЕДЁРНИ %s" % (n, n),
                   [PY, "-u", "tools/catch_fwupg.py", "--serial", a.serial, "--file", a.modfw,
                    "--wait", "1500"]):
            return 1
    if not run("плата %s, шаг 3/3: скетч в ESP32 — ПЕРЕДЁРНИ %s" % (n, n),
               fl + ["--file", a.app]):
        return 1
    print("=== %s: плата %s готова (до передёргивания — в загрузчике)" % (time.strftime("%H:%M:%S"), n),
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
