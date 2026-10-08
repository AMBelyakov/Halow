#!/usr/bin/env python3
"""
Смена адреса назначения у прозрачного транспорта uart_p2p прямо в образе прошивки.

    python tools/p2p_dest.py check SDK/builds/APP_..._384000-....bin
    python tools/p2p_dest.py set   SDK/builds/APP_..._384000-....bin \
        --mac c6:e8:35:70:7a:68 --out SDK/builds/APP_..._dest-ap.bin --yes

ЗАЧЕМ ЭТО НУЖНО

uart_p2p шлёт видео на ff:ff:ff:ff:ff:ff. Широковещательные кадры никто не
подтверждает — значит нет ни повторов, ни обратной связи, а без обратной связи
модуль не может подбирать модуляцию и обязан ставить заведомо живучую (MCS 0).
Отсюда и характер наших потерь: пакеты пропадают целиком при нулевой порче
байтов, потому что у каждого ровно одна попытка.

Разбор 04.09 показал, что MAC назначения — это ШЕСТЬ БАЙТ ДАННЫХ, а не
константа внутри инструкции:

    uart_p2p_task (0x2001d9f8):  lrw r8, 0x20059e50   <- указатель на dest
    по 0x20059e50:              ff ff ff ff ff ff 00 00 00 00 00 00 00 00 01 01

Подставив туда MAC соседней платы, получаем одноадресную передачу, а с ней
подтверждения, повторы и штатный автоподбор модуляции. Транспорт при этом не
трогаем — он закрыт, исходника нет.

ПОЧЕМУ ПРАВИМ ОБРАЗ, А НЕ ИСХОДНИК

Пересобирать модуль ради опыта незачем и рискованно. Шестнадцатибайтная
сигнатура встречается в образе РОВНО ОДИН РАЗ, поэтому её можно найти и
заменить в готовом бинарнике. Это снимает весь риск сборки: заливаем то же
самое, что уже проверено, с шестью изменёнными байтами.

ЧТО НЕ МЕНЯЕТСЯ И ПОЧЕМУ ЭТОГО ДОСТАТОЧНО

dest_ip (255.255.255.255) и порты 61234 зашиты в код инструкциями movi/subi, их
так не поправить. И не надо: подтверждения в 802.11 определяются адресом
КАНАЛЬНОГО уровня, а не содержимым IP-заголовка. Кадр с одноадресным получателем
будет подтверждён и повторён, даже если внутри лежит IP-широковещание.

Приёмная сторона его примет: uart_p2p_proc_rx (0x2001dbb8) проверяет только
IP-протокол 17 и порты 61234/61234, проверки на широковещательность там нет.

ОТКАТ

Залить исходный образ обратно. Заливка идёт во второй слот, активный не
трогается — проверено 03.09 на оборванной заливке: после срыва поднялась
прежняя сборка.
"""

import argparse
import hashlib
import os
import re
import struct
import sys

# Шестнадцать байт по 0x20059e50 в ЗАВОДСКОЙ сборке. Шести байт ff мало:
# в образе их 337 штук, а вся сигнатура целиком — ровно одна.
SIGNATURE = bytes.fromhex("ffffffffffff" + "0000000000000000" + "0101")
BROADCAST = b"\xff" * 6

# Хвост той же сигнатуры, без первых шести байт. Он переживает правку, поэтому
# по нему находится и уже правленый образ. В одиночку опорой не годится —
# встречается пять раз, — поэтому работает только вместе с адресом из
# дизассемблера, который выбирает нужное вхождение.
TAIL = SIGNATURE[6:]
MAC_LEN = 6

# Заголовок годного APP-образа. Тот же, что проверяет fwupg.py.
APP_MAGIC = bytes.fromhex("695a001c")

# Разница между адресом в ОЗУ и смещением в файле для этого семейства сборок:
# 0x20059e50 - 0x05ae50. Служит перекрёстной проверкой того, что сигнатура
# найдена там, где надо, а не совпала со случайными данными.
LOAD_DELTA = 0x1FFFF000

# КОНТРОЛЬНАЯ СУММА ОБРАЗА.
#
# 05.09, дорогой ценой: первая правка образа не взлетела, потому что в
# заголовке лежит CRC тела, а мы её не пересчитали. Загрузчик отверг образ,
# модуль не поднялся, AT молчал — и это два дня выглядело как «одноадресная
# передача ломает связь». Опыт при этом вообще не состоялся.
#
# Алгоритм восстановлен перебором и проверен на ВСЕХ тринадцати заводских
# сборках в SDK/builds: CRC16-MODBUS (отражённый, полином 0xA001, начальное
# 0xFFFF) по телу образа, начиная со смещения 0x2000 и до конца файла.
# Результат лежит в младших 16 битах поля +0x14; старшие 16 бит там константа
# 0x0010 и не трогаются.
#
# Поле +0x1c тоже меняется от сборки к сборке, но воспроизвести его перебором
# не удалось — возможно, это не сумма, а идентификатор сборки. Мы его не
# трогаем; если окажется, что загрузчик сверяет и его, образ не поднимется, и
# это будет видно сразу.
CRC_OFF = 0x14          # где лежит сумма
BODY_OFF = 0x2000       # с какого смещения считается тело
CRC_POLY = 0xA001
CRC_INIT = 0xFFFF

# Дизассемблер той сборки, из которой берём адрес для сверки.
# Путь считаем от корня репозитория, а не от текущего каталога: инструмент
# одинаково часто запускают и из корня, и из tools/.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ASM = os.path.join(_REPO, "SDK", "extracted2", "wnb",
                           "TXW8301_WNB-v2.4.1.3-43933", "project", "Lst",
                           "txw4002a.asm")


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


def image_crc(data):
    """CRC16-MODBUS по телу образа — та сумма, что лежит в заголовке."""
    crc = CRC_INIT
    for b in data[BODY_OFF:]:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ CRC_POLY if crc & 1 else crc >> 1
    return crc


def header_crc(data):
    """Что записано в заголовке (младшие 16 бит поля +0x14)."""
    return struct.unpack_from("<I", data, CRC_OFF)[0] & 0xFFFF


def set_header_crc(data, crc):
    """Положить сумму в заголовок, сохранив старшие 16 бит поля."""
    word = struct.unpack_from("<I", data, CRC_OFF)[0]
    struct.pack_into("<I", data, CRC_OFF, (word & 0xFFFF0000) | (crc & 0xFFFF))


def fmt_mac(raw):
    return ":".join("%02x" % b for b in raw)


def parse_mac(text):
    parts = re.split(r"[:\-]", text.strip())
    if len(parts) != 6:
        raise ValueError("MAC должен быть из шести байт: %r" % text)
    try:
        raw = bytes(int(p, 16) for p in parts)
    except ValueError:
        raise ValueError("MAC должен быть шестнадцатеричным: %r" % text)
    if raw == BROADCAST:
        raise ValueError("это широковещательный адрес — так уже и есть, "
                         "смысла в правке нет")
    if raw[0] & 0x01:
        raise ValueError("младший бит первого байта взведён — это групповой "
                         "адрес, подтверждений по нему не будет: %s"
                         % fmt_mac(raw))
    return raw


def asm_dest_addr(path):
    """Адрес dest из дизассемблера: первый lrw на 0x2005xxxx в uart_p2p_task.

    Нужен не сам по себе, а как независимая опора: если сигнатура совпала со
    случайными данными, разница «адрес минус смещение» не сойдётся.
    Возвращает None, если файла нет — сверка тогда пропускается.
    """
    if not os.path.exists(path):
        return None
    inside = False
    with open(path, "r", errors="ignore") as fh:
        for line in fh:
            if "<uart_p2p_task>:" in line:
                inside = True
                continue
            if inside:
                # конец функции — начался следующий символ
                if re.match(r"^[0-9a-f]{8} <", line):
                    break
                m = re.search(r"lrw\s+r\d+,\s*0x(2005[0-9a-f]{4})", line)
                if m:
                    return int(m.group(1), 16)
    return None


def locate(data, image_path, asm_path):
    """Найти шесть байт адреса назначения. Возвращает (смещение, текущий MAC).

    Каждая проверка закрывает свой способ ошибиться, поэтому ни одна не лишняя.
    """
    if data[:4] != APP_MAGIC:
        raise RuntimeError("заголовок не %s — это не APP-образ. Шить param.bin "
                           "или txw8301.bin нельзя, там MAC и калибровка."
                           % fmt_mac(APP_MAGIC).replace(":", " "))

    addr = asm_dest_addr(asm_path)

    # Путь основной: адрес берём из дизассемблера, а хвост сигнатуры служит
    # подтверждением, что по этому смещению действительно наши шестнадцать
    # байт. Работает и на правленом образе — первые шесть байт в опору не
    # входят.
    if addr is not None:
        off = addr - LOAD_DELTA
        if not (0 <= off <= len(data) - len(SIGNATURE)):
            raise RuntimeError(
                "адрес 0x%08x даёт смещение 0x%x вне образа. Дизассемблер от "
                "другой сборки?" % (addr, off))
        if data[off + MAC_LEN:off + len(SIGNATURE)] != TAIL:
            raise RuntimeError(
                "по смещению 0x%06x (адрес 0x%08x) нет ожидаемого хвоста "
                "сигнатуры. Дизассемблер не от этого образа — сверьте, что "
                "%s собран из того же дерева." % (off, addr, image_path))
        print("  опора: адрес 0x%08x из дизассемблера = смещение 0x%06x, "
              "хвост сигнатуры на месте" % (addr, off))
        return off, data[off:off + MAC_LEN]

    # Запасной путь: дизассемблера нет. Тогда ищем всю сигнатуру целиком —
    # она уникальна, но существует только у НЕправленого образа.
    print("  ВНИМАНИЕ: %s не найден, ищу по полной сигнатуре" % asm_path)
    hits = []
    i = data.find(SIGNATURE)
    while i >= 0:
        hits.append(i)
        i = data.find(SIGNATURE, i + 1)

    if not hits:
        raise RuntimeError(
            "сигнатура не найдена. Скорее всего образ уже правлен: без "
            "дизассемблера правленый не опознать, первые шесть байт в нём "
            "другие. Укажите --asm от той же сборки.")
    if len(hits) > 1:
        raise RuntimeError("сигнатура встречается %d раз, а должна один. "
                           "Правка вслепую испортит образ." % len(hits))

    return hits[0], data[hits[0]:hits[0] + MAC_LEN]


def md5(data):
    return hashlib.md5(data).hexdigest()


def cmd_check(args):
    data = open(args.image, "rb").read()
    print("образ:  %s" % args.image)
    print("размер: %d байт, md5 %s" % (len(data), md5(data)))
    try:
        off, cur = locate(data, args.image, args.asm)
    except RuntimeError as e:
        print("\nОТКАЗ: %s" % e)
        return 1
    print("\nMAC назначения: %s" % fmt_mac(cur))
    print("смещение в файле: 0x%06x" % off)
    if cur == BROADCAST:
        print("это широковещательный адрес — образ заводской, не правленый")
    else:
        print("образ правлен на одноадресную передачу")

    want, have = image_crc(data), header_crc(data)
    print("")
    print("CRC тела: посчитано %04x, в заголовке %04x" % (want, have))
    if want == have:
        print("сумма сходится — загрузчик образ примет")
        return 0
    print("СУММА НЕ СХОДИТСЯ. Загрузчик такой образ отвергнет, модуль не")
    print("поднимется и будет молчать на AT. Ровно так 04.09 выглядело")
    print("«одноадресность сломала связь» — а опыт просто не состоялся.")
    return 1


SLOTS = (0x000000, 0x080000)      # два слота приложения, по 512 КБ
PARAMS = (0x0FE000, 0x0FF000)     # параметры: MAC и калибровка, ТРОГАТЬ НЕЛЬЗЯ


def cmd_slots(args):
    """Разобрать дамп флеша модуля: что в слотах и какой из них годен.

    Нужно при восстановлении после неудачной заливки. AT+FWUPG пишет образ в
    свободный слот и снимает метку годности со старого; если новый образ не
    проходит CRC, загрузчику становится нечего запускать. Тогда по дампу надо
    понять, где лежит целая прошивка, и вернуть метку ей.

    Раньше «какой слот годный» определялось по косвенным признакам. Теперь —
    точно: у годного сходится CRC тела с заголовком.
    """
    d = open(args.dump, "rb").read()
    print("дамп: %s, %d байт (%.1f МБ)" % (args.dump, len(d), len(d) / 1048576.0))
    print("")

    good = []
    for i, base in enumerate(SLOTS):
        print("--- слот %d, смещение 0x%06x ---" % (i, base))
        if base + 0x2000 > len(d):
            print("    дамп короче слота, пропускаю")
            continue
        hdr = d[base:base + 4]
        marked = hdr == APP_MAGIC
        print("    метка годности: %s %s"
              % (" ".join("%02x" % c for c in hdr),
                 "— годен к загрузке" if marked else "— СНЯТА, загрузчик его не возьмёт"))

        length = struct.unpack_from("<I", d, base + 0x10)[0]
        total = 0x2000 + length
        if total > 512 * 1024 or base + total > len(d):
            print("    длина 0x%x бессмысленна — слот пуст или испорчен" % length)
            continue
        body = d[base:base + total]
        crc, want = image_crc(body), header_crc(body)
        ok = crc == want
        print("    длина тела: 0x%x, образ целиком 0x%x" % (length, total))
        print("    CRC: посчитано %04x, в заголовке %04x — %s"
              % (crc, want, "СХОДИТСЯ" if ok else "не сходится, образ битый"))
        print("    md5 образа: %s" % md5(body))
        try:
            off, mac = locate(body, args.dump, args.asm)
            print("    MAC назначения uart_p2p: %s" % fmt_mac(mac))
        except RuntimeError:
            pass
        if ok:
            good.append((i, base, marked))
        print("")

    print("=== что делать ===")
    if not good:
        print("Целых образов нет ни в одном слоте. Восстанавливать нечего —")
        print("нужно заливать прошивку из SDK/builds целиком.")
        return 1
    for i, base, marked in good:
        if marked:
            print("Слот %d цел И помечен годным. Модуль должен грузиться с него;" % i)
            print("если не грузится, дело не в метках.")
            return 0
    i, base, _ = good[0]
    print("Слот %d цел, но метка с него СНЯТА — это и есть наш случай." % i)
    print("Починка: восстановить в 0x%06x четыре байта %s"
          % (base, " ".join("%02x" % c for c in APP_MAGIC)))
    print("и обнулить метку у второго слота.")
    print("")
    print("ВАЖНО: метку нельзя вернуть простой записью — нужны переходы 0->1,")
    print("то есть стирание сектора 4 КБ. Стирать только сектор слота.")
    print("Область параметров 0x%06x/0x%06x НЕ ТРОГАТЬ: там MAC и калибровка,"
          % PARAMS)
    print("уникальные для этого чипа, восстановить их неоткуда.")
    return 0


def analyse_slots(d, dump_path, asm_path):
    """Разобрать оба слота. Возвращает список (номер, смещение, помечен, цел)."""
    out = []
    for i, base in enumerate(SLOTS):
        if base + 0x2000 > len(d):
            continue
        marked = d[base:base + 4] == APP_MAGIC
        length = struct.unpack_from("<I", d, base + 0x10)[0]
        total = 0x2000 + length
        ok = False
        if total <= 512 * 1024 and base + total <= len(d):
            body = d[base:base + total]
            ok = image_crc(body) == header_crc(body)
        out.append((i, base, marked, ok))
    return out


def cmd_fixslots(args):
    """Собрать исправленный дамп: метку — годному слоту, ноль — битому.

    Отдельная команда, чтобы не редактировать байты руками. На выходе полный
    образ флеша, который программатор пишет целиком: раз он сделан из вашего же
    дампа, область параметров с MAC и калибровкой переносится один в один.
    """
    d = bytearray(open(args.dump, "rb").read())
    slots = analyse_slots(d, args.dump, args.asm)

    good = [s for s in slots if s[3]]
    if not good:
        print("ОТКАЗ: целых образов нет ни в одном слоте — чинить нечего.")
        print("Придётся заливать прошивку из SDK/builds целиком.")
        return 1

    if args.slot is not None:
        # Явный выбор. Нужен, когда целы ОБА слота и надо решить, какой из них
        # поднимать: так бывает после заливки образа с верной суммой, который
        # загрузчик всё равно не взял.
        pick = [x for x in good if x[0] == args.slot]
        if not pick:
            print("ОТКАЗ: слот %d не цел или его нет. Целые слоты: %s"
                  % (args.slot, ", ".join(str(x[0]) for x in good)))
            return 1
        gi, gbase = pick[0][0], pick[0][1]
        print("слот выбран явно ключом --slot")
    else:
        if any(x[2] for x in good):
            i = [x[0] for x in good if x[2]][0]
            print("Слот %d уже цел И помечен годным." % i)
            if len(good) > 1:
                print("Но целых слотов несколько: %s."
                      % ", ".join(str(x[0]) for x in good))
                print("Если грузиться должен ДРУГОЙ — укажите его: --slot N.")
                print("Какой где, видно по команде slots: там для каждого")
                print("печатается MAC назначения uart_p2p.")
            else:
                print("Если модуль не грузится, причина не в метках.")
            return 1
        gi, gbase = good[0][0], good[0][1]
    print("годный слот: %d (0x%06x) — вернём ему метку" % (gi, gbase))
    for i, base, marked, ok in slots:
        if i != gi and marked:
            print("битый слот:  %d (0x%06x) — снимем метку" % (i, base))

    before = bytes(d)
    d[gbase:gbase + 4] = APP_MAGIC
    for i, base, marked, ok in slots:
        if i != gi:
            d[base:base + 4] = b"\x00\x00\x00\x00"
    out = bytes(d)

    # Параметры обязаны совпасть побайтно: там MAC и калибровка этого чипа.
    for base in PARAMS:
        if base + 4096 <= len(out) and out[base:base + 4096] != before[base:base + 4096]:
            print("ОТКАЗ: область параметров 0x%06x изменилась — это ошибка." % base)
            return 1

    diff = [i for i in range(len(out)) if out[i] != before[i]]
    print("")
    print("изменено байт: %d — %s" % (len(diff), " ".join("0x%x" % x for x in diff)))
    print("параметры 0x%06x/0x%06x: не тронуты, сверено побайтно" % PARAMS)

    if not args.yes:
        print("")
        print("Ничего не записано: нужен --yes.")
        return 1

    with open(args.out, "wb") as fh:
        fh.write(out)
    print("")
    print("готово: %s" % args.out)
    print("  размер %d, md5 %s" % (len(out), md5(out)))
    print("")
    print("Писать программатором ЦЕЛИКОМ. Дамп ваш собственный, поэтому")
    print("параметры вернутся на место сами и стирание всего чипа безопасно.")
    print("После записи — verify, потом чип в кроватку и проверить AT.")
    return 0


def cmd_set(args):
    data = bytearray(open(args.image, "rb").read())
    src_md5 = md5(bytes(data))
    print("исходный образ: %s" % args.image)
    print("  размер %d, md5 %s" % (len(data), src_md5))

    try:
        new_mac = parse_mac(args.mac)
        off, cur = locate(bytes(data), args.image, args.asm)
    except (RuntimeError, ValueError) as e:
        print("\nОТКАЗ: %s" % e)
        return 1

    if cur != BROADCAST:
        print("\nОТКАЗ: там уже %s, а не широковещательный адрес. Правим "
              "только заводской образ, чтобы не наслаивать правки друг на "
              "друга." % fmt_mac(cur))
        return 1

    if os.path.exists(args.out) and not args.force:
        print("\nОТКАЗ: %s уже существует. Удалите или дайте --force." % args.out)
        return 1

    print("\nбудет записано:")
    print("  смещение 0x%06x: %s -> %s" % (off, fmt_mac(cur), fmt_mac(new_mac)))
    print("  результат: %s" % args.out)

    if not args.yes:
        print("\nНичего не сделано: нужен --yes.")
        return 1

    data[off:off + MAC_LEN] = new_mac

    # Пересчитываем CRC тела. Без этого загрузчик отвергает образ, модуль не
    # поднимается и молчит на AT — проверено на себе 04.09, см. комментарий
    # к CRC_OFF. Правка шести байт без пересчёта суммы бесполезна.
    old_crc = header_crc(bytes(data))
    crc = image_crc(bytes(data))
    set_header_crc(data, crc)
    print("  CRC тела в заголовке: %04x -> %04x" % (old_crc, crc))
    out = bytes(data)

    # Перечитываем то, что получилось, тем же кодом, что и проверяли. Дешевле
    # убедиться здесь, чем на плате после минуты заливки.
    if len(out) != len(data):
        print("ОТКАЗ: размер изменился")
        return 1
    if out[:4] != APP_MAGIC:
        print("ОТКАЗ: заголовок испорчен")
        return 1
    if out[off:off + MAC_LEN] != new_mac:
        print("ОТКАЗ: запись не легла")
        return 1
    if image_crc(out) != header_crc(out):
        print("ОТКАЗ: CRC не сошлась после записи")
        return 1

    with open(args.out, "wb") as fh:
        fh.write(out)

    print("\nготово.")
    print("  размер %d (не изменился), md5 %s" % (len(out), md5(out)))
    print("  проверить: python tools/p2p_dest.py check %s" % args.out)
    print("\nЗаливать в модуль ТОЙ платы, которая должна слать одноадресно:")
    print("  python tools/fwupg.py --port COMx --file %s --yes" % args.out)
    print("Плата должна быть под мостом и заново включена — иначе AT+NOP2P не")
    print("попадёт в стартовое окно модуля и AT не оживёт.")
    return 0


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser("check", help="показать текущий MAC назначения")
    c.add_argument("image")
    c.add_argument("--asm", default=DEFAULT_ASM)
    c.set_defaults(func=cmd_check)

    sl = sub.add_parser("slots", help="разобрать дамп флеша: что в слотах и какой годен")
    sl.add_argument("dump", help="файл дампа из flash_tool.py read")
    sl.add_argument("--asm", default=DEFAULT_ASM)
    sl.set_defaults(func=cmd_slots)

    fx = sub.add_parser("fixslots", help="собрать исправленный дамп для программатора")
    fx.add_argument("dump", help="дамп, снятый программатором ДО правок")
    fx.add_argument("--out", required=True, help="куда положить исправленный дамп")
    fx.add_argument("--asm", default=DEFAULT_ASM)
    fx.add_argument("--slot", type=int, choices=(0, 1), default=None,
                    help="какой слот сделать загрузочным (когда целы оба)")
    fx.add_argument("--yes", action="store_true", help="подтверждение записи файла")
    fx.set_defaults(func=cmd_fixslots)

    s = sub.add_parser("set", help="записать MAC соседней платы")
    s.add_argument("image")
    s.add_argument("--mac", required=True, help="MAC получателя, xx:xx:xx:xx:xx:xx")
    s.add_argument("--out", required=True, help="куда положить правленый образ")
    s.add_argument("--asm", default=DEFAULT_ASM)
    s.add_argument("--yes", action="store_true",
                   help="подтверждение: пишем образ прошивки")
    s.add_argument("--force", action="store_true", help="перезаписать --out")
    s.set_defaults(func=cmd_set)

    args = p.parse_args()
    if not getattr(args, "func", None):
        p.print_help()
        return 2
    target = getattr(args, "image", None) or getattr(args, "dump", None)
    if not os.path.exists(target):
        print("нет файла: %s" % target)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
