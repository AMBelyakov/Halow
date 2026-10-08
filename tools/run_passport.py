#!/usr/bin/env python3
"""
Паспорт прогона: что именно было залито и с какими настройками.

Зачем. В разборе 24-27.08 два прогона дали противоречивые результаты — с
шифрованием камера подключалась за три секунды и слетала на рукопожатии, без
шифрования не подключалась вовсе. Разобрать это противоречие нельзя, потому
что конфигурация прогонов нигде не записана: настройки скетчей менялись
десятками правок, прошивки модулей — семью сборками, параметры модулей — АТ
командами по ходу дела. Прогон без паспорта — это не измерение, а анекдот.

Инструмент собирает в один файл всё, что делает прогон воспроизводимым:

  * состояние репозитория (ветка, коммит, есть ли несохранённые правки);
  * какой скетч сейчас активен в platformio.ini;
  * значения #define обоих скетчей — тех, что влияют на результат;
  * md5 и даты собранных прошивок модуля в SDK/builds;
  * md5 собранного firmware.bin, если сборка свежая;
  * снимки конфигурации обеих плат (tools/halow_at.py dump), если они есть.

    python tools/run_passport.py --note "откат параметров, LOADDEF на обеих"
    python tools/run_passport.py --ap tools/logs/syscfg_ap_...txt \
                                 --sta tools/logs/syscfg_sta_...txt

Файл кладётся в tools/logs/passport_<время>.txt рядом с CSV просмотрщика, и
его имя стоит упомянуть в --note самого просмотрщика — тогда запись и паспорт
сходятся по времени.
"""

import argparse
import glob
import hashlib
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGDIR = os.path.join(ROOT, "tools", "logs")

STA_INO = os.path.join(ROOT, "examples", "HalowVideoP2P_STA",
                       "HalowVideoP2P_STA.ino")
AP_INO = os.path.join(ROOT, "examples", "HalowVideoP2P_AP",
                      "HalowVideoP2P_AP.ino")

# Только те #define, которые способны изменить исход прогона. Полный список
# был бы нечитаем, а короткий — бесполезен; здесь ровно те, вокруг которых
# крутился весь разбор.
WATCHED = [
    # UART и стартовое окно — на рассинхроне окон 27.08 сгорели двое суток
    "AT_BAUD", "P2P_BAUD", "MODULE_P2P_DELAY_MS", "P2P_WINDOW_MS",
    # что скетч делает с модулем при загрузке
    "USE_AT_WINDOW", "AT_WINDOW_WRITE", "AT_WINDOW_LOGCFG", "AT_WINDOW_READ",
    "QUIET_MODULE", "LINK_DIAG", "SET_MCAST", "MCAST_BW", "MCAST_MCS",
    "TX_POWER",
    # гейт передачи
    "WAIT_FOR_HELLO", "HELLO_WAIT_MAX_MS", "RESTREAM_ON_HELLO_LOSS",
    "HELLO_LOST_MS", "LINK_TIMEOUT_MS", "STAT_PERIOD_MS",
    # камера и сжатие
    "FRAME_SIZE", "CAM_XCLK_HZ", "JPEG_QUALITY_SW", "PIPELINE",
    "ENCODE_FROM_SRAM",
    # транспорт
    "CHUNK_GAP_MS", "FRAME_GAP_MS", "CHUNK_PAYLOAD",
    # режимы замеров и диагностики: если хоть один взведён, прогон особый
    "GAP_SWEEP", "PAYLOAD_SWEEP", "TEST_PATTERN", "DUMP_RAW", "DUMP_JPEG",
    "CHECK_FB", "CHECK_ENCODER", "CHECK_COPY", "BAUD_HUNT",
]


def sh(*args):
    try:
        out = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                             timeout=20)
        return out.stdout.strip() or out.stderr.strip()
    except Exception as e:
        return "(не удалось: %s)" % e


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def defines(path):
    """Собрать значения #define из скетча.

    Значение берётся как есть, включая выражения вроде
    (MODULE_P2P_DELAY_MS + 3000): подставлять числа не нужно, важно увидеть
    связь между окном и задержкой прошивки. Комментарий в конце строки
    отбрасывается.
    """
    found = {}
    if not os.path.exists(path):
        return found
    pat = re.compile(r"^\s*#define\s+([A-Z_][A-Z0-9_]*)\s+(.+?)\s*$")
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = pat.match(line)
            if not m:
                continue
            name, val = m.group(1), m.group(2)
            val = re.sub(r"\s*(//|/\*).*$", "", val).strip()
            if name in WATCHED:
                found[name] = val
    return found


def active_src_dir():
    ini = os.path.join(ROOT, "platformio.ini")
    if not os.path.exists(ini):
        return "(нет platformio.ini)"
    with open(ini, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^\s*src_dir\s*=\s*(\S+)", line)
            if m:
                return m.group(1)
    return "(не задан)"


def newest(pattern):
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--note", default="", help="чем этот прогон отличается")
    p.add_argument("--ap", help="снимок конфигурации приёмника (halow_at.py dump)")
    p.add_argument("--sta", help="снимок конфигурации камеры")
    p.add_argument("--no-auto-dumps", action="store_true",
                   help="не подхватывать последние снимки автоматически")
    args = p.parse_args()

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = []
    add = out.append

    add("=" * 72)
    add("ПАСПОРТ ПРОГОНА T-Halow")
    add("время: %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    if args.note:
        add("что проверяем: %s" % args.note)
    add("=" * 72)
    add("")

    add("--- репозиторий")
    add("ветка:  %s" % sh("git", "rev-parse", "--abbrev-ref", "HEAD"))
    add("коммит: %s" % sh("git", "rev-parse", "--short", "HEAD"))
    dirty = sh("git", "status", "--porcelain")
    add("несохранённые правки: %s" % ("ЕСТЬ" if dirty else "нет"))
    if dirty:
        for line in dirty.split("\n")[:40]:
            add("    " + line)
    add("")

    add("--- сборка ESP32")
    add("активный src_dir: %s" % active_src_dir())
    fw = os.path.join(ROOT, ".pio", "build", "T-Halow", "firmware.bin")
    if os.path.exists(fw):
        add("firmware.bin: %s  %s  %d байт"
            % (md5(fw),
               time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(fw))),
               os.path.getsize(fw)))
    else:
        add("firmware.bin: нет (не собирали в этой копии)")
    add("")

    add("--- прошивки модуля (SDK/builds)")
    bins = sorted(glob.glob(os.path.join(ROOT, "SDK", "builds", "*.bin")),
                  key=os.path.getmtime)
    if not bins:
        add("(нет)")
    for b in bins:
        add("%-58s %s  %s"
            % (os.path.basename(b), md5(b),
               time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(b)))))
    add("")
    add("ВНИМАНИЕ: какая из сборок реально работает в модуле, по этому списку")
    add("не видно — заливка идёт во второй слот, и активный слот выбирается при")
    add("загрузке. Различать пробой AT+VERSION в стартовом окне.")
    add("")

    for title, path in (("КАМЕРА (STA)", STA_INO), ("ПРИЁМНИК (AP)", AP_INO)):
        add("--- настройки скетча: %s" % title)
        add("файл: %s" % os.path.relpath(path, ROOT))
        d = defines(path)
        if not d:
            add("(не удалось прочитать)")
        for name in WATCHED:
            if name in d:
                add("    %-24s %s" % (name, d[name]))
        add("")

    # Согласованность окна и задержки прошивки — то, на чём сгорели трое суток.
    sta_d, ap_d = defines(STA_INO), defines(AP_INO)
    add("--- проверка согласованности")
    for title, d in (("камера", sta_d), ("приёмник", ap_d)):
        delay = d.get("MODULE_P2P_DELAY_MS")
        window = d.get("P2P_WINDOW_MS")
        if delay and window:
            linked = "MODULE_P2P_DELAY_MS" in window
            add("%-10s окно=%s при задержке модуля %s -> %s"
                % (title, window, delay,
                   "считается от задержки, разъехаться не может" if linked
                   else "ЗАДАНО ЧИСЛОМ, сверить вручную"))
        else:
            add("%-10s не удалось прочитать окно/задержку" % title)
    if sta_d.get("MODULE_P2P_DELAY_MS") != ap_d.get("MODULE_P2P_DELAY_MS"):
        add("ВНИМАНИЕ: платы объявляют РАЗНУЮ задержку прозрачного режима.")
        add("Это законно только если в модули залиты разные сборки.")
    if sta_d.get("P2P_BAUD") != ap_d.get("P2P_BAUD"):
        add("ВНИМАНИЕ: P2P_BAUD у плат различается — поток не соберётся.")
    add("")

    ap_dump = args.ap
    sta_dump = args.sta
    if not args.no_auto_dumps:
        ap_dump = ap_dump or newest(os.path.join(LOGDIR, "syscfg_ap_*.txt"))
        sta_dump = sta_dump or newest(os.path.join(LOGDIR, "syscfg_sta_*.txt"))

    for title, path in (("ПРИЁМНИК (AP)", ap_dump), ("КАМЕРА (STA)", sta_dump)):
        add("--- конфигурация модуля: %s" % title)
        if not path or not os.path.exists(path):
            add("(снимка нет — снять командой tools/halow_at.py dump)")
            add("")
            continue
        age_h = (time.time() - os.path.getmtime(path)) / 3600.0
        add("файл: %s (снят %.1f ч назад)" % (os.path.relpath(path, ROOT), age_h))
        if age_h > 12:
            add("ВНИМАНИЕ: снимок старый, конфигурация могла успеть измениться.")
        with open(path, encoding="utf-8") as f:
            add(f.read().rstrip())
        add("")

    os.makedirs(LOGDIR, exist_ok=True)
    dest = os.path.join(LOGDIR, "passport_%s.txt" % stamp)
    text = "\n".join(out) + "\n"
    with open(dest, "w", encoding="utf-8") as f:
        f.write(text)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(text)
    print("Паспорт сохранён: %s" % dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
