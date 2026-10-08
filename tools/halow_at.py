#!/usr/bin/env python3
"""
AT-команды модулю TX-AH через сервисный мост (examples/HalowPassthrough).

Зачем этот инструмент. На прозрачной прошивке модуль нем: AT живёт только в
стартовом окне. Всё, что мы знали о состоянии линка за три дня разбора, снято
с точки доступа — станция оставалась чёрным ящиком. Здесь собраны операции,
которых не хватало:

    dump   — снять конфигурацию платы целиком, НИЧЕГО не меняя
    diff   — сравнить два снимка и показать, чем платы разошлись
    setup  — сбросить параметры к заводским и заново задать рецепт 13.08
    scan   — спросить станцию, видит ли она точку доступа
    send   — послать одну произвольную команду

Мост должен быть залит в ту плату, чей модуль опрашиваем:
    src_dir = examples/HalowPassthrough  ->  pio run -t upload
Мост сам шлёт AT+NOP2P при старте, поэтому AT доступен без ограничения по
времени. Скорость всегда 115200: в atcmd.c:242 она зашита литералом, и
аварийное окно не зависит от UART_P2P_BAUDRATE.

    python tools/halow_at.py dump  --port COM7 --name ap
    python tools/halow_at.py dump  --port COM9 --name sta
    python tools/halow_at.py diff  tools/logs/syscfg_ap_...txt tools/logs/syscfg_sta_...txt
    python tools/halow_at.py setup --port COM7 --role ap  --yes
    python tools/halow_at.py setup --port COM9 --role sta --yes

ЧЕГО ЗДЕСЬ НАРОЧНО НЕТ

AT+PAIR не опрашивается. У команды нет режима чтения: обработчик
(sdk/lib/common/atcmd.c:398) делает os_atoi(argv[0]), и "?" превращается в 0,
то есть в "Stop pairing!" плюс вызов ieee80211_pairing(ifidx, 0). Запрос на
чтение молча оказался бы записью. Состояние спаривания видно в AT+SYSCFG —
строка "Pair STAs" или "No pair STAs".

AT+SCAN вынесен в отдельную подкоманду и требует --yes: сканирование рвёт
уже установленную связь.
"""

import argparse
import os
import re
import sys
import time

LOGDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def _console_utf8():
    """Не дать русскому выводу превратиться в кракозябры.

    Консоль Windows по умолчанию в cp866, и всё, что печатается ниже, в ней
    нечитаемо. Файлы снимков пишутся в UTF-8 всегда, здесь чиним только вывод.
    Любая ошибка глушится: инструмент должен работать и там, где эти вызовы
    недоступны (перенаправление в файл, не-Windows, старый Python).
    """
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

# Чтение конфигурации. Ни одна из этих команд не меняет состояние модуля.
READ_CMDS = [
    "AT+VERSION",
    "AT+SYSCFG",        # конфигурация целиком: mac, bssid, bss_bw, chan_list,
                        # ssid, passwd, key_mgmt, bss_max_idle, dhcpc/dhcpd,
                        # список Pair STAs (project/syscfg.c:325)
    "AT+MAC_ADDR=?",
    "AT+WIFIMODE=?",
    "AT+SSID=?",
    "AT+ENCRYPT=?",
    "AT+BSS_BW=?",
    "AT+CHAN_LIST=?",
    "AT+CHANNEL=?",
    "AT+TXPOWER=?",
    "AT+AP_PSMODE=?",
    "AT+SLEEP_EN=?",
    "AT+RADIO_ONOFF=?",
    "AT+ACK_TO=?",
    "AT+MCAST_BW=?",
    "AT+MCAST_MCS=?",
    # Состояние линка и счётчики PHY. RX_PKTS против RX_ERR отделяет
    # "слышу энергию, но не декодирую" (расхождение полосы) от
    # "декодирую, но отказываю в ассоциации" (спаривание, bssid, ключи).
    "AT+STA_INFO=?",
    "AT+RSSI=?",
    "AT+RX_PKTS=?",
    "AT+RX_ERR=?",
    "AT+TX_PKTS=?",
    "AT+TX_FAIL=?",
]

# Поля AT+SYSCFG, которые на двух платах ОБЯЗАНЫ совпадать. Расхождение любого
# из них само по себе объясняет "точка доступа станцию слышит, ассоциации нет".
MUST_MATCH = [
    "bss_bw", "chan_list", "chan_cnt", "ssid", "passwd", "key_mgmt",
    "bss_max_idle", "beacon_int", "dtim_period", "ack_tmo",
]
# Поля, которые обязаны различаться или различаются законно.
EXPECTED_DIFF = ["mac", "mode", "ipaddr", "AP default", "dhcpd_start_ip"]


def open_serial_quiet(port, baud=115200, timeout=0.2):
    """Открыть порт, не дёргая DTR/RTS.

    pyserial поднимает линии в момент открытия, и плата успевает
    перезагрузиться. Настройки применяются при открытии, поэтому выставляем
    их заранее — тот же приём, что в tools/halow_viewer.py.
    """
    import serial
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = timeout
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser


def drain(ser, seconds=0.3):
    """Выбросить всё, что мост уже накопил: баннер и загрузочный лог модуля."""
    end = time.time() + seconds
    junk = b""
    while time.time() < end:
        junk += ser.read(4096)
    return junk.decode("utf-8", "ignore")


def at(ser, cmd, timeout=3.0, quiet=0.35, echo=True):
    """Послать одну команду и собрать ответ.

    Ждём терминатора OK/ERROR, но не только его: часть команд отвечает без
    него, а AT+SSID при неизменившемся значении печатает "set same ssid" и
    OK не даёт вовсе. Поэтому вторым условием — пауза на линии.
    """
    ser.reset_input_buffer()
    ser.write((cmd + "\r\n").encode("ascii"))
    ser.flush()

    buf = b""
    t0 = time.time()
    last = t0
    while time.time() - t0 < timeout:
        chunk = ser.read(4096)
        if chunk:
            buf += chunk
            last = time.time()
            if re.search(r"(^|[\r\n])(OK|ERROR)\s*([\r\n]|$)",
                         buf.decode("utf-8", "ignore")):
                # Дать дописаться хвосту: OK иногда приходит раньше последних
                # строк многострочного ответа.
                time.sleep(0.15)
                buf += ser.read(4096)
                break
        elif buf and time.time() - last > quiet:
            break

    text = buf.decode("utf-8", "ignore").replace("\r\n", "\n").strip()
    if echo:
        if "\n" in text:
            print("  %s ->" % cmd)
            for line in text.split("\n"):
                print("      " + line)
        else:
            print("  %s -> %s" % (cmd, text if text else "(нет ответа)"))
    return text


def ok(text):
    """Считать ли ответ успешным."""
    if not text:
        return False
    if "ERROR" in text:
        return False
    # AT+SSID= при неизменившемся значении не отвечает OK — это не ошибка.
    return "OK" in text or "set same ssid" in text


def nop2p(ser, tries=8, gap=0.4):
    """Отменить отложенный старт прозрачного режима.

    Нужно после каждой перезагрузки модуля: мост шлёт NOP2P только при своём
    старте, а AT+LOADDEF и AT+RST перезагружают модуль, и отсчёт задержки
    начинается заново.
    """
    for _ in range(tries):
        ser.write(b"AT+NOP2P\r\n")
        ser.flush()
        time.sleep(gap)
        if b"OK" in ser.read(4096):
            print("  AT+NOP2P принят — AT-режим закреплён")
            return True
    print("  AT+NOP2P без ответа (прошивка без прозрачного режима — это нормально)")
    return False


# ------------------------------- dump ---------------------------------------

def cmd_dump(args):
    ser = open_serial_quiet(args.port)
    try:
        pre = drain(ser, 0.5)
        if args.nop2p:
            nop2p(ser)

        stamp = time.strftime("%Y%m%d_%H%M%S")
        os.makedirs(LOGDIR, exist_ok=True)
        path = os.path.join(LOGDIR, "syscfg_%s_%s.txt" % (args.name, stamp))

        print("Снимаю конфигурацию с %s (%s), только чтение" % (args.port, args.name))
        out = ["# T-Halow: снимок конфигурации модуля",
               "# плата: %s" % args.name,
               "# порт: %s" % args.port,
               "# снято: %s" % time.strftime("%Y-%m-%d %H:%M:%S"),
               ""]
        if pre.strip():
            out += ["## накопленный вывод до опроса", pre.strip(), ""]

        for c in READ_CMDS:
            text = at(ser, c, timeout=4.0 if c == "AT+SYSCFG" else 2.5)
            out.append("=== %s" % c)
            out.append(text if text else "(нет ответа)")
            out.append("")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        print("")
        print("Снимок сохранён: %s" % path)
        return 0
    finally:
        ser.close()


# ------------------------------- diff ---------------------------------------

def parse_dump(path):
    """Разобрать снимок в словарь команда -> ответ."""
    blocks = {}
    cur = None
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("=== "):
                if cur:
                    blocks[cur] = "\n".join(lines).strip()
                cur = line[4:].strip()
                lines = []
            elif cur is not None:
                lines.append(line)
    if cur:
        blocks[cur] = "\n".join(lines).strip()
    return blocks


def syscfg_fields(text):
    """Вытащить из ответа AT+SYSCFG пары поле -> значение.

    Формат печати — "  ключ:значение, ключ:значение" (project/syscfg.c:325),
    плюс несколько строк особого вида: chan_list и список Pair STAs.
    """
    fields = {}
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("chan_list:"):
            fields["chan_list"] = line.split(":", 1)[1].split(",")[0].strip()
            m = re.search(r"chan_cnt:\s*(\S+)", line)
            if m:
                fields["chan_cnt"] = m.group(1)
            continue
        if line.startswith("STA") and re.search(r"[0-9a-fA-F]{2}:", line):
            fields.setdefault("pair_stas", []).append(line)
            continue
        if line in ("No pair STAs", "Pair STAs:"):
            fields["pair_stas_hdr"] = line
            continue
        for key, val in re.findall(r"([A-Za-z_][A-Za-z0-9_ ]*?):\s*([^,]+)", line):
            key, val = key.strip(), val.strip()
            if key and val:
                fields[key] = val
    if isinstance(fields.get("pair_stas"), list):
        fields["pair_stas"] = " ".join(fields["pair_stas"])
    return fields


def cmd_diff(args):
    fa, fb = parse_dump(args.file_a), parse_dump(args.file_b)
    print("A = %s" % args.file_a)
    print("B = %s" % args.file_b)
    print("")

    sa = syscfg_fields(fa.get("AT+SYSCFG", ""))
    sb = syscfg_fields(fb.get("AT+SYSCFG", ""))
    if not sa or not sb:
        print("ВНИМАНИЕ: в одном из снимков нет разбираемого AT+SYSCFG")

    must, expected, other, same = [], [], [], []
    for k in sorted(set(sa) | set(sb)):
        va, vb = sa.get(k, "(нет)"), sb.get(k, "(нет)")
        if va == vb:
            same.append(k)
        elif any(k.startswith(p) for p in MUST_MATCH):
            must.append((k, va, vb))
        elif any(k.startswith(p) for p in EXPECTED_DIFF):
            expected.append((k, va, vb))
        else:
            other.append((k, va, vb))

    def show(title, rows):
        print(title)
        if not rows:
            print("    (пусто)")
        for k, va, vb in rows:
            print("    %-18s A=%-28s B=%s" % (k, va, vb))
        print("")

    show("РАСХОЖДЕНИЯ, КОТОРЫХ БЫТЬ НЕ ДОЛЖНО (на них линк и ломается):", must)
    show("Расхождения ожидаемые (роль, адрес, MAC):", expected)
    show("Прочие расхождения — смотреть глазами:", other)
    print("Совпадают: %s" % (", ".join(same) if same else "(нет)"))
    print("")

    # Спаривание. Флаг pair_conn_only в дампе не печатается, но список
    # Pair STAs — да. Если список непустой, а MAC второй платы в него не
    # входит, точка доступа откажет в ассоциации молча: без add_STA и без
    # попытки аутентификации (sys_ieee80211_event_pairsta в прошивке
    # возвращает ненулевой код для MAC не из списка).
    for name, s, peer in (("A", sa, sb), ("B", sb, sa)):
        if s.get("pair_stas_hdr") == "Pair STAs:":
            peer_mac = peer.get("mac", "").lower()
            lst = s.get("pair_stas", "").lower()
            found = bool(peer_mac) and peer_mac in lst
            print("Спаривание на %s: список непустой, MAC второй платы в нём %s"
                  % (name, "есть" if found else "НЕТ"))
            print("    %s" % s.get("pair_stas", ""))
            if not found:
                print("    -> если взведён pair_conn_only, ассоциация будет")
                print("       отклоняться молча. Лечится AT+LOADDEF (setup).")
    print("")

    print("Команды, ответы на которые различаются (кроме AT+SYSCFG):")
    any_diff = False
    for c in READ_CMDS:
        if c == "AT+SYSCFG":
            continue
        ra, rb = fa.get(c, "(нет)"), fb.get(c, "(нет)")
        if ra != rb:
            any_diff = True
            print("    %-18s A=%-26s B=%s" % (c,
                                              ra.replace("\n", " ")[:26],
                                              rb.replace("\n", " ")[:40]))
    if not any_diff:
        print("    (нет)")
    return 0


# ------------------------------- setup --------------------------------------

def cmd_setup(args):
    """Рецепт 13.08: сброс к заводским и пять команд, по одной, с проверкой.

    Почему сначала параметры, а не откат прошивки. 13.08 связь встала не от
    прошивки, а после AT+LOADDEF и этих пяти команд. Разница прошивок
    13.08 -> 26.08 — это netlog=0 (измеренно полезен) и задержка. Разница
    параметров — шифрование, спаривание, mcast, txpower и, возможно, SSID/PSK
    и BSSID, переписанные процедурой спаривания.

    AT+LOADDEF возвращает заводские значения на обеих платах одинаково:
    KEYMGMT=2, cipher CCMP, пароль 12345678, родной MAC из UUID. Поэтому
    шифрование сходится само и трогать AT+ENCRYPT не нужно.
    """
    if not args.yes:
        print("AT+LOADDEF стирает параметрическую область модуля: шифрование,")
        print("спаривание, SSID, полосу, канал — всё вернётся к заводскому.")
        print("Калибровка RF и MAC не затрагиваются: MAC берётся из UUID.")
        print("Подтвердите ключом --yes.")
        return 1

    ser = open_serial_quiet(args.port)
    try:
        drain(ser, 0.5)
        nop2p(ser)

        print("")
        print("--- состояние ДО сброса")
        before = at(ser, "AT+SYSCFG", timeout=4.0)

        print("")
        print("--- AT+LOADDEF (сброс к заводским, модуль перезагрузится)")
        at(ser, "AT+LOADDEF", timeout=3.0)
        print("  жду перезагрузку модуля...")
        time.sleep(args.reboot_wait)
        drain(ser, 1.0)
        nop2p(ser)

        # Порядок и синтаксис — из рецепта 13.08. Команды идут ПО ОДНОЙ и с
        # ожиданием ответа: вставка списком склеивает их в терминале
        # ("AT+CHAN_LIST=8660ow_video"), и конфигурация пишется мусором.
        recipe = [
            "AT+SSID=%s" % args.ssid,
            "AT+CHAN_LIST=%s" % args.chan_list,   # в десятых МГц: 8660 = 866.0
            "AT+BSS_BW=%s" % args.bss_bw,
            "AT+WIFIMODE=%s" % args.role,         # в 2.4 роль задаёт WIFIMODE,
        ]                                         # команды AT+MODE в SDK 2.4 нет
        if args.ap_psmode and args.role == "ap":
            # Не входит в проверенный рецепт 13.08, поэтому только по флагу:
            # одна заливка — одна переменная. Значение сохраняется само
            # (syscfg_save в обработчике), повторять при каждом старте не надо.
            recipe.append("AT+AP_PSMODE=0")

        print("")
        print("--- рецепт")
        failed = []
        for c in recipe:
            if not ok(at(ser, c, timeout=3.0)):
                failed.append(c)
            time.sleep(0.3)

        if failed:
            print("")
            print("НЕ ПРИНЯТЫ: %s" % ", ".join(failed))
            print("Повторите их по одной вручную (send), не перезагружая модуль.")

        print("")
        print("--- состояние ПОСЛЕ рецепта, до перезагрузки")
        after = at(ser, "AT+SYSCFG", timeout=4.0)

        print("")
        print("--- AT+RST")
        at(ser, "AT+RST", timeout=2.0)
        time.sleep(args.reboot_wait)
        drain(ser, 1.0)
        nop2p(ser)
        print("")
        print("--- состояние ПОСЛЕ перезагрузки (это и есть рабочее)")
        final = at(ser, "AT+SYSCFG", timeout=4.0)

        stamp = time.strftime("%Y%m%d_%H%M%S")
        os.makedirs(LOGDIR, exist_ok=True)
        path = os.path.join(LOGDIR, "setup_%s_%s.txt" % (args.role, stamp))
        with open(path, "w", encoding="utf-8") as f:
            f.write("# setup %s, %s\n\n"
                    % (args.role, time.strftime("%Y-%m-%d %H:%M:%S")))
            f.write("=== ДО\n%s\n\n=== ПОСЛЕ РЕЦЕПТА\n%s\n\n=== ПОСЛЕ RST\n%s\n"
                    % (before, after, final))
        print("")
        print("Протокол сохранён: %s" % path)
        print("Теперь снимите dump с ОБЕИХ плат и сравните командой diff.")
        return 1 if failed else 0
    finally:
        ser.close()


# ------------------------------- прочее -------------------------------------

def cmd_scan(args):
    if not args.yes:
        print("AT+SCAN рвёт уже установленную связь: модуль уходит перебирать")
        print("каналы. Делать на станции, когда линка нет. Подтвердите --yes.")
        return 1
    ser = open_serial_quiet(args.port)
    try:
        drain(ser, 0.5)
        nop2p(ser)
        print("Сканирую — это единственный способ узнать, видит ли станция AP")
        at(ser, "AT+SCAN", timeout=args.timeout)
    finally:
        ser.close()
    return 0


def cmd_reset(args):
    """AT+RST и НЕМЕДЛЕННОЕ повторное закрепление AT-режима.

    Отдельная команда, потому что просто послать AT+RST — ловушка, и я в неё
    попал 27.08. Модуль перезагружается, отсчёт UART_P2P_START_DELAY_MS
    начинается заново, а мост шлёт AT+NOP2P только при собственной загрузке.
    ESP32 при перезагрузке модуля не перезагружается, повторить NOP2P некому,
    и через задержку модуль забирает UART. После этого AT не вернуть ничем,
    кроме снятия питания с платы: линии сброса к модулю на плате нет, только
    UART на GPIO4/5.
    """
    ser = open_serial_quiet(args.port)
    try:
        drain(ser, 0.4)
        print("--- AT+RST")
        at(ser, "AT+RST", timeout=3.0)
        print("  жду перезагрузку модуля...")
        time.sleep(args.wait)
        drain(ser, 0.5)
        if not nop2p(ser, tries=15, gap=0.4):
            print("  ВНИМАНИЕ: NOP2P не подтверждён. Если прошивка с прозрачным")
            print("  режимом, AT пропадёт через UART_P2P_START_DELAY_MS, и")
            print("  вернуть его можно будет только снятием питания с платы.")
            return 1
        at(ser, "AT+VERSION", timeout=3.0)
    finally:
        ser.close()
    return 0


def cmd_listen(args):
    """Слушать модуль и печатать его лог с отметками времени.

    Нужно для событий, которые никакой командой не спросишь: add_STA,
    состояния WPA, установка ключей, LMAC STATUS с очередью отправки.
    """
    keep = [k for k in (args.grep or "").split(",") if k]
    buf = b""
    print("Слушаю %s %.0f с%s" % (args.port, args.seconds,
                                  (", фильтр: " + ",".join(keep)) if keep else ""))
    sys.stdout.flush()

    # Ждём появления порта, а не падаем на нём.
    #
    # Главный сценарий этой команды — поймать загрузочный лог: запись ставят
    # ЗАРАНЕЕ, а платы обесточивают уже после. 28.08 слушатель из-за этого
    # упал на open() и пропустил ровно то включение, ради которого ставился.
    ser = None
    t_wait = time.time()
    while ser is None:
        try:
            ser = open_serial_quiet(args.port)
        except Exception:
            if time.time() - t_wait > args.wait_port:
                print("Порт %s не появился за %.0f с" % (args.port, args.wait_port))
                return 1
            time.sleep(0.5)
    if time.time() - t_wait > 1.0:
        print("  [порт появился через %.1f с]" % (time.time() - t_wait))
        sys.stdout.flush()
    t0 = time.time()
    try:
        while time.time() - t0 < args.seconds:
            try:
                buf += ser.read(4096)
            except Exception as e:
                # USB этой платы периодически отваливается на доли секунды.
                # 27.08 такой провал оборвал измерение на середине; терять
                # длинный прогон из-за него нельзя, поэтому переоткрываем.
                print("%7.1f  [порт отвалился: %s, переоткрываю]"
                      % (time.time() - t0, type(e).__name__))
                sys.stdout.flush()
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                # Опрашиваем часто: плата грузится и печатает первые строки
                # за пару секунд, и при паузе в полсекунды между попытками
                # начало загрузки терялось. 01.09 из-за этого пропало три
                # включения из пяти в серии по ширине канала.
                while ser is None and time.time() - t0 < args.seconds:
                    time.sleep(0.02)
                    try:
                        ser = open_serial_quiet(args.port)
                        print("%7.1f  [порт вернулся]" % (time.time() - t0))
                        sys.stdout.flush()
                    except Exception:
                        ser = None
                if ser is None:
                    break
                continue
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                txt = line.decode("utf-8", "ignore").rstrip()
                # Модуль красит часть строк ANSI-последовательностями,
                # в лог они попадают мусором.
                txt = "".join(ch for ch in txt if ch.isprintable())
                if not txt.strip():
                    continue
                if keep and not any(k in txt for k in keep):
                    continue
                print("%7.1f  %s" % (time.time() - t0, txt.strip()))
                sys.stdout.flush()
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
    return 0


def cmd_send(args):
    ser = open_serial_quiet(args.port)
    try:
        drain(ser, 0.4)
        for c in args.cmd:
            if "RST" in c.upper() or "LOADDEF" in c.upper():
                print("  ОТКАЗ: %s перезагружает модуль. Используйте подкоманду" % c)
                print("  reset (или setup) — они повторяют AT+NOP2P после сброса.")
                continue
            at(ser, c, timeout=args.timeout)
            time.sleep(0.2)
    finally:
        ser.close()
    return 0


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="what")

    d = sub.add_parser("dump", help="снять конфигурацию (только чтение)")
    d.add_argument("--port", required=True)
    d.add_argument("--name", default="board", help="ap, sta или любое имя файла")
    d.add_argument("--no-nop2p", dest="nop2p", action="store_false",
                   help="не слать AT+NOP2P (прошивка без прозрачного режима)")
    d.set_defaults(func=cmd_dump)

    f = sub.add_parser("diff", help="сравнить два снимка")
    f.add_argument("file_a")
    f.add_argument("file_b")
    f.set_defaults(func=cmd_diff)

    s = sub.add_parser("setup", help="AT+LOADDEF и рецепт 13.08")
    s.add_argument("--port", required=True)
    s.add_argument("--role", required=True, choices=["ap", "sta"])
    s.add_argument("--ssid", default="halow_video")
    s.add_argument("--chan-list", dest="chan_list", default="8660")
    s.add_argument("--bss-bw", dest="bss_bw", default="8")
    s.add_argument("--ap-psmode", action="store_true",
                   help="дополнительно выключить энергосбережение AP; не входит "
                        "в проверенный рецепт — это отдельная переменная")
    s.add_argument("--reboot-wait", type=float, default=10.0)
    s.add_argument("--yes", action="store_true")
    s.set_defaults(func=cmd_setup)

    c = sub.add_parser("scan", help="AT+SCAN на станции")
    c.add_argument("--port", required=True)
    c.add_argument("--timeout", type=float, default=15.0)
    c.add_argument("--yes", action="store_true")
    c.set_defaults(func=cmd_scan)

    r = sub.add_parser("reset", help="AT+RST с повторным закреплением AT-режима")
    r.add_argument("--port", required=True)
    r.add_argument("--wait", type=float, default=8.0)
    r.set_defaults(func=cmd_reset)

    l = sub.add_parser("listen", help="слушать лог модуля")
    l.add_argument("--port", required=True)
    l.add_argument("--seconds", type=float, default=60.0)
    l.add_argument("--wait-port", dest="wait_port", type=float, default=180.0,
                   help="сколько ждать появления порта перед началом записи; "
                        "отсчёт времени идёт от момента, когда порт появился")
    l.add_argument("--grep", help="печатать только строки с этими подстроками "
                                  "через запятую, например add_STA,WPA,buf:")
    l.set_defaults(func=cmd_listen)

    e = sub.add_parser("send", help="послать произвольные команды")
    e.add_argument("--port", required=True)
    e.add_argument("--timeout", type=float, default=3.0)
    e.add_argument("cmd", nargs="+")
    e.set_defaults(func=cmd_send)

    args = p.parse_args()
    if not args.what:
        p.print_help()
        return 2
    if args.what != "diff":
        try:
            import serial  # noqa: F401
        except ImportError:
            print("Нужен pyserial: pip install pyserial")
            return 2
    rc = args.func(args)
    return rc if isinstance(rc, int) else 0


if __name__ == "__main__":
    sys.exit(main())
