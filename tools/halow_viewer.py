#!/usr/bin/env python3
"""
Просмотрщик видео T-Halow.

Плата с камерой шлёт JPEG кусками через AT+TXDATA. Приёмная плата (HalowVideo_AP)
вычленяет их из "+RXDATA" и гонит в USB-Serial — это РАБОЧИЙ путь доставки до ПК
(--serial-video COMx, нужен pyserial). RJ45-мост модуля для таких инжектированных
кадров не работает (см. память thalow-delivery-usb-not-rj45) — UDP-режим ниже
оставлен на случай прошивки модуля, которая это когда-нибудь исправит, но
на практике молчит.

Нужен только Python 3.8+ (стандартная библиотека) плюс pyserial для --serial-video.

    python tools/halow_viewer.py --serial-video COM7   # видео+метрики из USB приёмника (рабочий)
    python tools/halow_viewer.py                        # видео из UDP (мост в RJ45, не работает)
    python tools/halow_viewer.py --serial COM7          # только RSSI приёмника (устар.)

Затем открыть http://localhost:8099

ЗАПИСЬ РЕЗУЛЬТАТОВ В CSV (для замеров диплома)

    python tools/halow_viewer.py --serial-video COM7 --csv --note 50m
    python tools/halow_viewer.py --serial-video COM7 --csv --no-http   # без браузера

Файл создаётся НЕ при запуске, а при первом принятом пакете — то есть при
первом коннекте плат. Поэтому t_s=0 в логе означает начало передачи, а не
момент, когда оператор нажал Enter и пошёл с платой на позицию.

Во время прогона можно вводить метки с клавиатуры: набрал "100m" и Enter —
метка попадёт в столбец marker этой строки и станет note для всех дальнейших.
Так один прогон режется на участки без остановки записи.

Каждая строка сразу сбрасывается на диск: севший аккумулятор не должен
стоить всего прогона.
"""

import argparse
import csv
import json
import os
import socket
import struct
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Должно совпадать с lib/HalowVideo/halow_proto.h
# 22 байта, метка HLW2: с 15.08 в заголовке есть frame_crc — контрольная
# сумма всего JPEG, посчитанная камерой. Сверяем её после склейки кадра.
APP_HDR = struct.Struct("<4sIIHHHHbB")
MAGIC = b"HLW2"
FLAG_LAST = 0x01
# 07.10, гибрид FEC + повтор (см. halow_proto.h). Кадр из K кусков по P байт идёт
# с M контрольными: кусок K+g — XOR кусков i с i % M == g (дополненных нулями до P).
FLAG_PARITY = 0x02
FLAG_RESEND = 0x04
FEC_M_SHIFT = 4
# Повтор старше этого числа кадров от показанного не бывает (у камеры кольцо
# на 6 кадров); номер меньше показанного больше чем на столько — камера
# перезагрузилась и считает заново.
LATE_SPAN = 16

# Кадрирование USB-моста приёмника (AP -> ПК), см. halow_proto.h:
#   [0xA5][0x5A][type][len_lo][len_hi][payload]
USB_SYNC = b"\xA5\x5A"
USB_TYPE_VIDEO = ord("V")
USB_TYPE_META = ord("M")
USB_TYPE_LOG = ord("L")     # 28.09: лог камеры по воздуху, тело = seq(2, LE) + текст


class AirLog:
    """
    Лог камеры, приехавший по радио (AIR_LOG в скетче камеры, 28.09).

    Камера копирует всю свою консоль в пакеты 'T', приёмник отдаёт их сюда
    записями 'L'. Пишем текст в tools/logs/cam_air_ДАТА_ВРЕМЯ_метка.txt —
    формат тот же, что у cam_console.py, так что отчёты читают оба файла, — и
    держим хвост строк для страницы. По seq видно потерю пакета и
    перезагрузку камеры (seq начинается с нуля).
    """

    TAIL = 400

    def __init__(self):
        import codecs
        self._codecs = codecs
        self.lock = threading.Lock()
        self.note = ""
        self.f = None
        self.path = None
        self.last_seq = None
        self.pkts = 0
        self.lost_pkts = 0
        self.restarts = 0
        self.last_at = None
        self.lines = deque(maxlen=self.TAIL)
        self.partial = ""
        self.dec = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.board = {}          # последние бортовые показания для страницы

    def _open(self):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.note)
        name = "cam_air_%s%s.txt" % (stamp, ("_" + safe) if safe else "")
        self.path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", name)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.f = open(self.path, "w", encoding="utf-8", newline="\n")
        print("Лог камеры по воздуху: пишу в %s" % self.path)

    def _mark(self, text):
        self._text("\n--- %s %s ---\n" % (text, time.strftime("%H:%M:%S")))

    def _text(self, s):
        self.f.write(s)
        s = self.partial + s
        parts = s.split("\n")
        self.partial = parts.pop()
        for ln in parts:
            ln = ln.rstrip("\r")
            if ln:
                self.lines.append(ln)
                self._parse(ln)

    def _parse(self, ln):
        import re
        b = self.board
        # 08.10: камера — точка доступа, приёмник у неё STA1 — строка tx1 (tx0 — старая схема).
        m = re.search(r"tx[01]: mcs=(\*?\d+) snr=(\d+) data=\S+\((\d+)kbps\) per=(\d+)", ln)
        if m and int(m.group(3)) > 5:
            b.update(mcs=m.group(1), air_kbps=int(m.group(3)), per=int(m.group(4)))
        m = re.search(r"PWRCTL snr=(-?\d+) .*?rx_snr=(-?\d+) rssi=(-?\d+) .*? pwr=(\d+)", ln)
        if m:
            b.update(snr=int(m.group(1)), rx_snr=int(m.group(2)), rssi=int(m.group(3)),
                     pwr=int(m.group(4)))
        m = re.search(r"MCSCTL snr=.* flr=(-?\d+) fph=", ln)
        if m:
            b.update(flr=int(m.group(1)))
        m = re.search(r"АВТОКАЧЕСТВО: \S+, Q=(\d+)", ln)
        if m:
            b.update(q=int(m.group(1)))
        m = re.search(r"РАЗРЕШЕНИЕ: ступень \d+ \((\d+x\d+)\)", ln)
        if m:
            b.update(cam_res=m.group(1))
        m = re.search(r"ПАУЗЫ-РЕЖИМ: (\S+), мощность", ln)
        if m:
            b.update(gate=m.group(1).rstrip(","))
        m = re.search(r"RTT ср (\d+) мин (\d+) макс (\d+)", ln)
        if m:
            b.update(rtt_max=int(m.group(3)))
        m = re.search(r"\[(связь|нет связи)\] ([\d.]+) fps", ln)
        if m:
            b.update(cam_fps=float(m.group(2)))
        m = re.search(r"(?:MCS-ПЕРЕБОР|ВАРИАНТ): (шаг \d+ из \d+, [^—]+)", ln)
        if m:
            b.update(sweep=m.group(1))

    def on_packet(self, payload):
        if len(payload) < 2:
            return
        seq = payload[0] | (payload[1] << 8)
        with self.lock:
            if self.f is None:
                self._open()
                self._mark("лог по воздуху открыт")
            if self.last_seq is not None:
                want = (self.last_seq + 1) & 0xFFFF
                if seq == 0 and self.last_seq != 0xFFFF:
                    self.restarts += 1
                    self.dec = self._codecs.getincrementaldecoder("utf-8")(errors="replace")
                    self._mark("КАМЕРА ПЕРЕЗАПУЩЕНА")
                elif seq != want:
                    gap = (seq - want) & 0xFFFF
                    self.lost_pkts += gap
                    self.dec = self._codecs.getincrementaldecoder("utf-8")(errors="replace")
                    self._mark("лог: потеряно пакетов %d" % gap)
            self.last_seq = seq
            self.pkts += 1
            self.last_at = time.time()
            self._text(self.dec.decode(payload[2:]))
            self.f.flush()

    def snapshot(self, n=60):
        with self.lock:
            return {
                "lines": list(self.lines)[-n:],
                "pkts": self.pkts,
                "lost": self.lost_pkts,
                "restarts": self.restarts,
                "age": (time.time() - self.last_at) if self.last_at else None,
                "board": dict(self.board),
            }


class ApConsole:
    """
    Текстовая консоль приёмника (28.09): всё, что лежит в USB-потоке вне
    записей — стартовое окно приёмника, DIAG, строки модуля. Раньше это
    выбрасывалось как мусор до синхромаркера. Пишем в
    tools/logs/ap_console_ДАТА_ВРЕМЯ_метка.txt, двоичный мусор отсеиваем.
    """

    def __init__(self):
        import codecs
        self.note = ""
        self.f = None
        self.dec = codecs.getincrementaldecoder("utf-8")(errors="ignore")

    def feed(self, data):
        if not data:
            return
        # Текст: печатные ASCII, переводы строк и байты UTF-8 (кириллица).
        keep = bytes(b for b in data if b >= 0x20 or b in (9, 10, 13))
        if not keep:
            return
        if self.f is None:
            stamp = time.strftime("%Y%m%d_%H%M%S")
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.note)
            name = "ap_console_%s%s.txt" % (stamp, ("_" + safe) if safe else "")
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.f = open(path, "w", encoding="utf-8", newline="")
            print("Консоль приёмника: пишу в %s" % path)
        self.f.write(self.dec.decode(keep))
        self.f.flush()


# Кадр считаем потерянным, если он не собрался за это время
FRAME_TIMEOUT_S = 2.0
# Скользящее окно для fps и битрейта
WINDOW_S = 5.0


def jpeg_size(data):
    """Достаёт разрешение из маркера SOF JPEG. Возвращает (w, h) или None."""
    i = 2
    n = len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        # SOF0..SOF15, кроме DHT(C4), JPGA(C8) и DAC(CC)
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + seg_len
    return None


class AviRecorder:
    """07.10: запись показанных кадров в AVI (MJPEG) сама, с первого кадра после связи.

    Файл на сеанс: поток пропал дольше GAP_S — файл закрывается, вернулся — новый.
    Кадры приходят неровно (5–9 к/с), AVI требует постоянной частоты: пишем FPS кадров в
    секунду, повторяя последний показанный — длительность в файле равна живой. Разрешение
    меняется на ходу (480×320 / 320×213 / 240×160) — всё приводим к размеру первого кадра
    сеанса (PIL). Заголовок переписывается раз в 2 с: если процесс убит, файл всё равно
    открывается (VLC); индекс idx1 дописывается при штатном закрытии.
    """
    FPS = 10
    GAP_S = 10.0
    MAX_BYTES = 900 * 1024 * 1024        # AVI 1.0 — до 1 ГБ, дальше новый файл

    def __init__(self, folder, note=""):
        self.folder = folder
        self.note = note
        self.f = None
        self.lock = threading.Lock()
        self.files = 0
        threading.Thread(target=self._watch, daemon=True).start()

    # --- служебное -------------------------------------------------------------
    def _hdr(self):
        w, h, n = self.w, self.h, self.n
        us = int(1000000 / self.FPS)
        avih = struct.pack("<14I", us, 0, 0, 0x10, n, 0, 1, 1 << 20, w, h, 0, 0, 0, 0)
        strh = struct.pack("<4s4sIHHIIIIIIIIhhhh", b"vids", b"MJPG", 0, 0, 0, 0, 1,
                           self.FPS, 0, n, 1 << 20, 0xFFFFFFFF, 0, 0, 0, w, h)
        strf = struct.pack("<IiiHH4sIiiII", 40, w, h, 1, 24, b"MJPG", w * h * 3, 0, 0, 0, 0)
        strl = b"strl" + b"strh" + struct.pack("<I", len(strh)) + strh + \
               b"strf" + struct.pack("<I", len(strf)) + strf
        hdrl = b"hdrl" + b"avih" + struct.pack("<I", len(avih)) + avih + \
               b"LIST" + struct.pack("<I", len(strl)) + strl
        return b"LIST" + struct.pack("<I", len(hdrl)) + hdrl

    def _patch(self):
        """Переписать размеры и число кадров (длина заголовка не меняется)."""
        end = self.f.tell()
        self.f.seek(0)
        self.f.write(b"RIFF" + struct.pack("<I", end - 8) + b"AVI ")
        self.f.write(self._hdr())
        self.f.write(b"LIST" + struct.pack("<I", end - self.movi_pos))
        self.f.seek(end)
        self.f.flush()

    def _open(self, jpeg, now):
        from PIL import Image  # noqa: F401  (проверяем заранее, что есть)
        size = jpeg_size(jpeg) or (480, 320)
        self.w, self.h = size
        os.makedirs(self.folder, exist_ok=True)
        name = time.strftime("halow_%Y%m%d_%H%M%S", time.localtime(now))
        if self.note:
            name += "_" + "".join(c if c.isalnum() or c in "-_" else "_" for c in self.note)
        self.path = os.path.join(self.folder, name + ".avi")
        self.f = open(self.path, "wb")
        self.n = 0
        self.index = []
        self.f.write(b"RIFF" + struct.pack("<I", 0) + b"AVI ")
        self.f.write(self._hdr())
        self.movi_pos = self.f.tell() + 8          # где fourcc 'movi'
        self.f.write(b"LIST" + struct.pack("<I", 0) + b"movi")
        self.t0 = now
        self.last = None
        self.last_t = now
        self.patch_t = now
        self.files += 1
        print("Запись видео: %s (%dx%d, %d к/с)" % (self.path, self.w, self.h, self.FPS))

    def _fit(self, jpeg):
        """Кадр другого размера — привести к размеру файла."""
        if jpeg_size(jpeg) == (self.w, self.h):
            return jpeg
        try:
            import io
            from PIL import Image
            im = Image.open(io.BytesIO(jpeg)).convert("RGB").resize((self.w, self.h))
            out = io.BytesIO()
            im.save(out, "JPEG", quality=90)
            return out.getvalue()
        except Exception:
            return None

    def _put(self, jpeg):
        pos = self.f.tell()
        self.f.write(b"00dc" + struct.pack("<I", len(jpeg)) + jpeg)
        if len(jpeg) & 1:
            self.f.write(b"\0")
        self.index.append((pos - self.movi_pos, len(jpeg)))
        self.n += 1

    def _close(self):
        if not self.f:
            return
        if self.last is not None:
            self._put(self.last)
        self._patch()
        idx = b"".join(b"00dc" + struct.pack("<III", 0x10, off, ln) for off, ln in self.index)
        self.f.write(b"idx1" + struct.pack("<I", len(idx)) + idx)
        end = self.f.tell()
        self.f.seek(4)
        self.f.write(struct.pack("<I", end - 8))
        self.f.close()
        print("Запись видео закрыта: %s, %.0f с, %.1f МБ"
              % (self.path, self.n / float(self.FPS), end / 1048576.0))
        self.f = None

    def _watch(self):
        while True:
            time.sleep(1.0)
            with self.lock:
                if self.f and time.time() - self.last_t > self.GAP_S:
                    self._close()

    # --- снаружи ---------------------------------------------------------------
    def add(self, jpeg, now):
        with self.lock:
            try:
                if self.f is None:
                    self._open(jpeg, now)
                fitted = self._fit(jpeg)
                if fitted is None:
                    return
                n = int((now - self.t0) * self.FPS)
                while self.last is not None and self.n < n:
                    self._put(self.last)              # показанный кадр держится до нового
                self.last = fitted
                self.last_t = now
                if now - self.patch_t >= 2.0:
                    self.patch_t = now
                    self._patch()
                if self.f.tell() > self.MAX_BYTES:
                    self._close()
            except Exception as e:                     # запись не должна ронять показ
                print("Запись видео: ошибка %r — выключаю" % (e,))
                try:
                    if self.f:
                        self.f.close()
                except Exception:
                    pass
                self.f = None
                self.add = lambda *a: None

    def close(self):
        with self.lock:
            self._close()


class State:
    """Собирает кадры из чанков и считает метрики. Потокобезопасен."""

    def __init__(self):
        self.lock = threading.Lock()
        self.frame_ready = threading.Condition(self.lock)
        self.airlog = AirLog()       # лог камеры по воздуху, запись 'L'
        self.apcon = ApConsole()     # текст приёмника вне записей

        self.pending = {}            # frame_id -> {chunks, cnt, len, first_seen}
        self.latest_jpeg = None
        self.latest_seq = 0
        self.recorder = None         # AviRecorder: запись показанных кадров

        self.frames_ok = 0
        self.frames_lost = 0
        self.chunks_rx = 0
        self.chunks_expected = 0
        self.bytes_total = 0         # всего принято байт полезной нагрузки

        self.frame_times = deque()   # метки времени собранных кадров
        self.byte_times = deque()    # (время, байты) принятых датаграмм

        self.sta_rssi = None
        self.ap_rssi = None
        self.ap_conn = None
        self.last_packet_at = None
        self.first_packet_at = None  # момент первого коннекта плат
        self.resolution = None

        # Счётчики приёмника из записи 'M'. На прошивке шага 3 (прозрачный
        # режим) это единственная диагностика линка: AT-команд там нет, RSSI
        # спросить не у кого, зато видно, сколько пакетов побилось по CRC.
        self.ap_ok = None
        self.ap_crc_err = None
        self.ap_len_err = None
        self.ap_junk = None
        self.ap_fwd = None
        # 24.09: сбои UART на приёме ESP32 приёмника (onReceiveError)
        self.ap_u_ovf = None
        self.ap_u_bfull = None
        self.ap_u_frame = None
        self.ap_u_brk = None

        # Настройки радио, прочитанные приёмником в стартовом окне и оттуда же
        # переданные в метриках. После закрытия окна модуль нем, спросить его
        # нельзя — поэтому значение едет с каждой записью 'M'.
        #
        # 01.09: без этого нельзя было отличить "правка порога не помогла" от
        # "порог не применился" — строка о нём печаталась в первые секунды и
        # терялась, если просмотрщик подключали сразу.
        self.ap_margin = None
        self.ap_bgr = None

        # Битые записи USB-потока приёмник->ПК. Единственное звено цепочки,
        # которое до 15.08 шло без проверки целостности.
        self.usb_crc_err = 0

        # Кадры, собравшиеся целиком, но не сошедшиеся по контрольной сумме
        # всего JPEG. Растёт => доставка портит кадр незаметно для остальных
        # проверок. Ноль при видимых артефактах => артефакты из камеры.
        self.frame_crc_err = 0

        # 07.10, гибрид FEC + повтор.
        #   playout_s — сколько собранный кадр ждёт более старый недособранный
        #   (вдруг его дошлют повтором). 0 — показывать сразу, как раньше.
        #   Показ всегда по порядку: кадр старше показанного не показываем
        #   (frames_late) — иначе повтор вернул бы картинку назад.
        self.playout_s = 0.0
        self.ready = {}              # frame_id -> (jpeg, когда собран)
        self.last_shown_id = None
        self.closed = deque(maxlen=128)   # собранные и просроченные номера
        self.closed_set = set()
        self.fec_m = 0               # контрольных в последнем кадре
        self.fec_saved = 0           # кадров собрано благодаря контрольным
        self.fec_chunks = 0          # кусков восстановлено
        self.resend_saved = 0        # кадров собрано благодаря повтору
        self.resend_rx = 0           # повторов принято
        self.parity_rx = 0           # контрольных принято
        self.frames_late = 0         # собраны, но старше показанного
        self.dup_rx = 0              # пакеты уже закрытых кадров
        self.useful_total = 0        # байт JPEG в показанных кадрах
        self.useful_times = deque()  # (время, байты) показанных кадров

    def on_packet(self, data):
        if len(data) < APP_HDR.size:
            return
        (magic, frame_id, frame_len, idx, cnt, plen,
         frame_crc, rssi, flags) = APP_HDR.unpack_from(data, 0)
        if magic != MAGIC:
            return
        payload = data[APP_HDR.size:APP_HDR.size + plen]
        if len(payload) != plen or cnt == 0:
            return

        parity = bool(flags & FLAG_PARITY)
        resend = bool(flags & FLAG_RESEND)
        m = (flags >> FEC_M_SHIFT) & 0x0F
        now = time.time()
        with self.lock:
            if self.first_packet_at is None:
                self.first_packet_at = now
            self.last_packet_at = now
            self.sta_rssi = rssi if rssi != 0 else None
            self.bytes_total += len(data)
            self.byte_times.append((now, len(data)))
            # 07.10: chunks_rx — только куски данных с первой попытки, чтобы
            # chunk_loss_pct осталась потерей канала, без контрольных и повторов.
            if parity:
                self.parity_rx += 1
            elif resend:
                self.resend_rx += 1
            else:
                self.chunks_rx += 1
                self.fec_m = m

            if frame_id in self.closed_set:
                self.dup_rx += 1         # кадр уже собран или просрочен
                self._expire(now)
                return
            entry = self.pending.get(frame_id)
            if entry is None:
                entry = {"chunks": {}, "cnt": cnt, "len": frame_len,
                         "crc": frame_crc, "first_seen": now,
                         "par": {}, "m": m, "plen": 0, "resend": False, "fec": 0}
                self.pending[frame_id] = entry
                self.chunks_expected += cnt
            if parity:
                if idx >= cnt:
                    entry["par"][idx - cnt] = payload
                    entry["plen"] = plen
                    entry["m"] = m
            elif idx < entry["cnt"]:
                if resend and idx not in entry["chunks"]:
                    entry["resend"] = True
                entry["chunks"][idx] = payload

            if len(entry["chunks"]) < entry["cnt"] and entry["par"]:
                entry["fec"] += self._fec_fill(entry)

            if len(entry["chunks"]) == entry["cnt"]:
                jpeg = b"".join(entry["chunks"][i] for i in range(entry["cnt"]))
                want_crc = entry["crc"]
                del self.pending[frame_id]
                self._close(frame_id)
                # Все чанки на месте, но содержимое всё равно может быть битым:
                # чанк приходит "целым" по длине, а байты внутри испорчены.
                #
                # Маркеры JPEG ловят только грубые случаи: FFD8 в начале и FFD9
                # в конце сохраняются, даже если испорчена середина. Именно
                # такой кадр и даёт "радугу" в плеере — декодер теряет
                # синхронизацию на повреждении, а дальше коэффициенты яркости
                # кодируются разностью от предыдущего блока, и ошибка уезжает
                # цветными полосами до конца картинки.
                #
                # Поэтому сверяем сквозную CRC всего кадра (поле frame_crc,
                # метка HLW2). До 14.09 она разбиралась, но НЕ ПРОВЕРЯЛАСЬ:
                # счётчик frame_crc_err всегда стоял на нуле, и из этого нуля
                # делался вывод, будто каждый показанный кадр побайтно совпал
                # с уехавшим. Вывод был не обеспечен ничем.
                #
                # Оговорка про длину: камера считает CRC как
                # halow_crc16(buf, (uint16_t)total_len), то есть кадры больше
                # 64 КБ она посчитала бы по усечённой длине. Наши кадры 2.6-7 КБ,
                # так что до этой границы далеко; при переходе на большее
                # разрешение проверить заново.
                if jpeg[:2] != b"\xff\xd8" or jpeg[-2:] != b"\xff\xd9":
                    self.frames_lost += 1
                elif crc16(jpeg) != want_crc:
                    self.frames_lost += 1
                    self.frame_crc_err += 1
                else:
                    # Понадобился повтор — кадр спасён повтором, даже если часть
                    # дыр закрыли контрольные; иначе, если закрывали, — FEC.
                    if entry["resend"]:
                        self.resend_saved += 1
                    elif entry["fec"]:
                        self.fec_saved += 1
                    self._complete(frame_id, jpeg, now)

            self._release(now)
            self._expire(now)

    def _close(self, fid):
        if len(self.closed) == self.closed.maxlen:
            self.closed_set.discard(self.closed[0])
        self.closed.append(fid)
        self.closed_set.add(fid)

    def _fec_fill(self, e):
        """Восстанавливает куски по контрольным: в группе g (i % M) нет ровно одного."""
        m, plen, k, total = e["m"], e["plen"], e["cnt"], e["len"]
        if not m or not plen:
            return 0
        n = 0
        for g, par in list(e["par"].items()):
            if g >= m:
                continue
            group = range(g, k, m)
            miss = [i for i in group if i not in e["chunks"]]
            if len(miss) != 1:
                continue
            acc = int.from_bytes(par, "little")
            for i in group:
                if i != miss[0]:
                    acc ^= int.from_bytes(e["chunks"][i], "little")
            i = miss[0]
            li = min(plen, total - i * plen)
            if li <= 0:
                continue
            e["chunks"][i] = acc.to_bytes(plen, "little")[:li]
            n += 1
        self.fec_chunks += n
        return n

    def _is_late(self, fid):
        if self.last_shown_id is None:
            return False
        back = self.last_shown_id - fid
        if back > LATE_SPAN:
            self.last_shown_id = None    # камера перезагрузилась, номера заново
            return False
        return back >= 0

    def _complete(self, fid, jpeg, now):
        if self._is_late(fid):
            self.frames_late += 1
            return
        self.ready[fid] = (jpeg, now)

    def _release(self, now):
        """Показ по порядку. Кадр ждёт, пока недособран более старый (не дольше playout_s)."""
        while self.ready:
            fid = min(self.ready)
            jpeg, t_done = self.ready[fid]
            if self._is_late(fid):
                del self.ready[fid]
                self.frames_late += 1
                continue
            if self.playout_s > 0 and now - t_done < self.playout_s:
                older = any(p < fid and (self.last_shown_id is None or p > self.last_shown_id)
                            for p in self.pending)
                if older:
                    break
            del self.ready[fid]
            self.last_shown_id = fid
            self._publish(jpeg, now)

    def _publish(self, jpeg, now):
        self.latest_jpeg = jpeg
        self.latest_seq += 1
        self.frames_ok += 1
        self.frame_times.append(now)
        self.useful_total += len(jpeg)
        self.useful_times.append((now, len(jpeg)))
        size = jpeg_size(jpeg)
        if size:
            self.resolution = size
        if self.recorder is not None:
            self.recorder.add(jpeg, now)
        self.frame_ready.notify_all()

    def _expire(self, now):
        """Выбрасывает кадры, чьи чанки так и не долетели."""
        stale = [fid for fid, e in self.pending.items()
                 if now - e["first_seen"] > FRAME_TIMEOUT_S]
        for fid in stale:
            del self.pending[fid]
            self._close(fid)
            self.frames_lost += 1

        cutoff = now - WINDOW_S
        while self.frame_times and self.frame_times[0] < cutoff:
            self.frame_times.popleft()
        while self.byte_times and self.byte_times[0][0] < cutoff:
            self.byte_times.popleft()
        while self.useful_times and self.useful_times[0][0] < cutoff:
            self.useful_times.popleft()

    def wait_frame(self, last_seq, timeout=5.0):
        with self.frame_ready:
            if self.latest_seq == last_seq:
                self.frame_ready.wait(timeout)
            return self.latest_jpeg, self.latest_seq

    def metrics(self):
        now = time.time()
        with self.lock:
            self._expire(now)
            span = WINDOW_S
            fps = len(self.frame_times) / span
            self._release(now)          # кадры, дождавшиеся playout_s без новых пакетов
            kbps = sum(b for _, b in self.byte_times) * 8 / span / 1000.0
            useful = sum(b for _, b in self.useful_times) * 8 / span / 1000.0
            loss = 0.0
            if self.chunks_expected:
                loss = max(0.0, 100.0 * (1 - self.chunks_rx / self.chunks_expected))
            age = None if self.last_packet_at is None else round(now - self.last_packet_at, 1)
            return {
                "sta_rssi": self.sta_rssi,
                "ap_rssi": self.ap_rssi,
                "ap_conn": self.ap_conn,
                "fps": round(fps, 1),
                "kbps": round(kbps, 1),
                "useful_kbps": round(useful, 1),
                "fec_m": self.fec_m,
                "frames_ok": self.frames_ok,
                "frames_lost": self.frames_lost,
                "chunk_loss_pct": round(loss, 1),
                "frame_bytes": len(self.latest_jpeg) if self.latest_jpeg else 0,
                "resolution": "%dx%d" % self.resolution if self.resolution else None,
                "last_packet_age_s": age,
                "online": age is not None and age < 3.0,
                "ap_crc_err": self.ap_crc_err,
                "ap_junk": self.ap_junk,
                "usb_crc_err": self.usb_crc_err,
                "frame_crc_err": self.frame_crc_err,
                "fec_saved": self.fec_saved,
                "resend_saved": self.resend_saved,
                "frames_late": self.frames_late,
                "rec_file": (os.path.basename(self.recorder.path)
                             if self.recorder is not None and self.recorder.f else None),
                "rec_s": (self.recorder.n // self.recorder.FPS
                          if self.recorder is not None and self.recorder.f else None),
            }

    def totals(self):
        """Сырые накопленные счётчики — для CSV. Без скользящих окон."""
        with self.lock:
            return {
                "first_packet_at": self.first_packet_at,
                "last_packet_at": self.last_packet_at,
                "frames_ok": self.frames_ok,
                "frames_lost": self.frames_lost,
                "chunks_rx": self.chunks_rx,
                "chunks_expected": self.chunks_expected,
                "bytes_total": self.bytes_total,
                "sta_rssi": self.sta_rssi,
                "ap_rssi": self.ap_rssi,
                "ap_conn": self.ap_conn,
                "ap_ok": self.ap_ok,
                "ap_crc_err": self.ap_crc_err,
                "ap_len_err": self.ap_len_err,
                "ap_junk": self.ap_junk,
                "ap_fwd": self.ap_fwd,
                "ap_u_ovf": self.ap_u_ovf,
                "ap_u_bfull": self.ap_u_bfull,
                "ap_u_frame": self.ap_u_frame,
                "ap_u_brk": self.ap_u_brk,
                "ap_margin": self.ap_margin,
                "ap_bgr": self.ap_bgr,
                "resolution": "%dx%d" % self.resolution if self.resolution else "",
                "frame_bytes": len(self.latest_jpeg) if self.latest_jpeg else 0,
                "usb_crc_err": self.usb_crc_err,
                "frame_crc_err": self.frame_crc_err,
                "useful_total": self.useful_total,
                "fec_m": self.fec_m,
                "fec_saved": self.fec_saved,
                "fec_chunks": self.fec_chunks,
                "resend_saved": self.resend_saved,
                "resend_rx": self.resend_rx,
                "parity_rx": self.parity_rx,
                "frames_late": self.frames_late,
                "dup_rx": self.dup_rx,
            }


PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>T-Halow video</title>
<style>
  body { margin:0; background:#12151a; color:#e6e9ef;
         font-family:system-ui,Segoe UI,Roboto,sans-serif; }
  .wrap { display:flex; flex-wrap:wrap; gap:20px; padding:20px; }
  .video { background:#000; border:1px solid #2a2f3a; border-radius:8px; padding:8px; }
  .video img { display:block; width:480px; max-width:90vw; image-rendering:pixelated; }
  .panel { min-width:260px; }
  h1 { font-size:18px; margin:0 0 14px; font-weight:600; }
  table { border-collapse:collapse; width:100%; font-size:14px; }
  td { padding:7px 10px; border-bottom:1px solid #232833; }
  td:first-child { color:#8b93a3; }
  td:last-child { text-align:right; font-variant-numeric:tabular-nums; }
  .dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:7px; }
  .up { background:#3ddc84; } .down { background:#e0505a; }
  .hint { margin-top:14px; font-size:12px; color:#6b7280; line-height:1.5; }
  .board { flex:1 1 100%; min-width:0; }
  .board h1 { margin-top:4px; }
  .board table { max-width:520px; margin-bottom:12px; }
  pre#airlog { margin:0; background:#0b0d11; border:1px solid #2a2f3a; border-radius:8px;
               padding:10px 12px; height:320px; overflow:auto; font-size:12px; line-height:1.45;
               color:#c9d1d9; white-space:pre-wrap; word-break:break-word; }
</style>
</head>
<body>
<div class="wrap">
  <div class="video"><img src="/stream.mjpg" alt="поток"></div>
  <div class="panel">
    <h1><span id="dot" class="dot down"></span><span id="status">нет данных</span></h1>
    <table>
      <tr><td>Кадров в секунду</td><td id="fps">—</td></tr>
      <tr><td>Принято</td><td id="kbps">—</td></tr>
      <tr><td>Полезных (показанные кадры)</td><td id="useful">—</td></tr>
      <tr><td>Разрешение</td><td id="resolution">—</td></tr>
      <tr><td>Размер кадра</td><td id="frame_bytes">—</td></tr>
      <tr><td>Кадров показано / потеряно</td><td id="frames">—</td></tr>
      <tr><td>Потеря кусков</td><td id="chunk_loss_pct">—</td></tr>
      <tr><td>Спасено кадров: FEC / досылкой</td><td id="saved">—</td></tr>
      <tr id="r_rec"><td>Запись видео</td><td id="rec">—</td></tr>
    </table>
    <div class="hint">Видео идёт через USB приёмника (<code>--serial-video COMx</code>).</div>
  </div>
  <div class="board">
    <h1><span id="bdot" class="dot down"></span>Борт: камера и её модуль (лог по радио)</h1>
    <table id="btab">
      <tr><td>Мощность передатчика</td><td id="b_pwr">—</td></tr>
      <tr><td>SNR: приёмник слышит камеру / камера слышит приёмник</td><td id="b_snr">—</td></tr>
      <tr><td>RSSI приёмника у камеры</td><td id="b_rssi">—</td></tr>
      <tr><td>Модуляция последней попытки (* — автоподбор)</td><td id="b_mcs">—</td></tr>
      <tr><td>Пол модуляции (по уровню сигнала)</td><td id="b_flr">—</td></tr>
      <tr><td>Повторы в эфире (PER)</td><td id="b_per">—</td></tr>
      <tr><td>Скорость в эфире (с повторами)</td><td id="b_air">—</td></tr>
      <tr><td>Качество JPEG / кадр камеры</td><td id="b_q">—</td></tr>
      <tr><td>Паузы съёмки (от 8 дБм)</td><td id="b_gate">—</td></tr>
      <tr><td>Кадров в секунду на борту</td><td id="b_fps">—</td></tr>
      <tr><td>Задержка подтверждения, макс</td><td id="b_rtt">—</td></tr>
      <tr><td>Пакетов лога / потеряно</td><td id="b_pk">—</td></tr>
    </table>
    <pre id="airlog">ждём лог камеры…</pre>
  </div>
</div>
<script>
/* 08.10: строка без значения скрыта — пустых полей на странице нет. */
function put(id, v) {
  const el = document.getElementById(id);
  const row = el.parentElement;
  const has = v !== undefined && v !== null && v !== '';
  el.textContent = has ? v : '';
  row.style.display = has ? '' : 'none';
}
async function tick() {
  try {
    const m = await (await fetch('/metrics')).json();
    const on = m.online;
    put('fps', on ? m.fps.toFixed(1) : null);
    put('kbps', on ? m.kbps.toFixed(0) + ' кбит/с' : null);
    put('useful', on ? m.useful_kbps.toFixed(0) + ' кбит/с' : null);
    put('resolution', m.resolution);
    put('frame_bytes', m.frame_bytes ? (m.frame_bytes / 1024).toFixed(1) + ' КБ' : null);
    put('frames', (m.frames_ok || m.frames_lost) ? m.frames_ok + ' / ' + m.frames_lost : null);
    put('chunk_loss_pct', (m.frames_ok || m.frames_lost) ? m.chunk_loss_pct.toFixed(1) + ' %' : null);
    put('saved', (m.frames_ok || m.frames_lost) ? m.fec_saved + ' / ' + m.resend_saved : null);
    put('rec', m.rec_file ? m.rec_file + ', ' + m.rec_s + ' с' : null);
    document.getElementById('dot').className = 'dot ' + (on ? 'up' : 'down');
    document.getElementById('status').textContent = on ? 'поток идёт' : 'нет данных от камеры';
  } catch (e) { /* сервер перезапускается — просто ждём */ }
}
tick(); setInterval(tick, 500);
async function airTick() {
  try {
    const a = await (await fetch('/airlog')).json();
    const b = a.board || {};
    const has = v => v !== undefined && v !== null;
    put('b_pwr', has(b.pwr) ? b.pwr + ' дБм' : null);
    put('b_snr', has(b.snr) ? b.snr + ' / ' + (has(b.rx_snr) ? b.rx_snr : '?') + ' дБ' : null);
    put('b_rssi', has(b.rssi) ? b.rssi + ' дБм' : null);
    put('b_mcs', has(b.mcs) ? b.mcs + (b.sweep ? '  (' + b.sweep + ')' : '') : null);
    put('b_flr', has(b.flr) ? (b.flr > 0 ? 'не ниже MCS ' + b.flr : 'снят') : null);
    put('b_per', has(b.per) ? b.per + ' %' : null);
    put('b_air', has(b.air_kbps) ? b.air_kbps + ' кбит/с' : null);
    put('b_q', has(b.q) ? 'Q' + b.q + (b.cam_res ? ', ' + b.cam_res : '') : null);
    put('b_gate', has(b.gate) ? b.gate : null);
    put('b_fps', has(b.cam_fps) ? b.cam_fps.toFixed(1) : null);
    put('b_rtt', has(b.rtt_max) ? b.rtt_max + ' мс' : null);
    put('b_pk', a.pkts ? a.pkts + ' / ' + a.lost : null);
    document.getElementById('bdot').className = 'dot ' + (a.age !== null && a.age < 5 ? 'up' : 'down');
    const pre = document.getElementById('airlog');
    const atEnd = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 20;
    if (a.lines.length) pre.textContent = a.lines.join('\\n');
    if (atEnd) pre.scrollTop = pre.scrollHeight;
  } catch (e) { }
}
airTick(); setInterval(airTick, 1000);
</script>
</body>
</html>
""".encode("utf-8")


# 07.10: задержка «стекло-стекло». Камеру направить на эту страницу: слева часы,
# справа видео. Камера снимает часы, видео показывает их с опозданием — разница
# двух чисел и есть полная задержка (съёмка, сжатие, эфир, ожидание показа, экран).
# «Снимок» (кнопка или пробел) замораживает кадр видео вместе с точным временем
# нажатия; часы в кадре читаются глазами, задержка = время нажатия − часы в кадре.
CLOCK_PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>T-Halow clock</title>
<style>
  body { margin:0; background:#fff; color:#000; font-family:Consolas,monospace; }
  .row { display:flex; gap:16px; padding:12px; align-items:flex-start; flex-wrap:wrap; }
  #clock { font-size:150px; font-weight:700; line-height:1; padding:16px 24px;
           border:6px solid #000; font-variant-numeric:tabular-nums; }
  .vid img, canvas { display:block; width:480px; max-width:90vw; border:2px solid #000; }
  .snaps { padding:0 12px 12px; display:flex; gap:16px; flex-wrap:wrap; }
  .snap { font-size:20px; }
  button { font-size:20px; padding:8px 16px; margin:0 12px; }
  .hint { font-family:system-ui,sans-serif; font-size:14px; color:#444; padding:0 12px; }
</style>
</head>
<body>
<div class="row">
  <div id="clock">00.000</div>
  <div class="vid"><img id="v" src="/stream.mjpg" alt="поток"></div>
</div>
<button id="b">Снимок (пробел)</button>
<div class="hint">Камера смотрит на часы слева. Задержка = «время снимка» − часы, видные в
  замороженном кадре. Сделайте 5–10 снимков.</div>
<div class="snaps" id="snaps"></div>
<script>
const c = document.getElementById('clock');
const fmt = t => { const s = (t / 1000) % 100; return (s < 10 ? '0' : '') + s.toFixed(3); };
function draw() { c.textContent = fmt(Date.now()); requestAnimationFrame(draw); }
draw();
function snap() {
  const t = Date.now();
  const v = document.getElementById('v');
  const cv = document.createElement('canvas');
  cv.width = v.naturalWidth || 480; cv.height = v.naturalHeight || 320;
  try { cv.getContext('2d').drawImage(v, 0, 0, cv.width, cv.height); } catch (e) {}
  const d = document.createElement('div'); d.className = 'snap';
  d.appendChild(cv);
  const p = document.createElement('div'); p.textContent = 'время снимка: ' + fmt(t);
  d.appendChild(p);
  const box = document.getElementById('snaps'); box.insertBefore(d, box.firstChild);
}
document.getElementById('b').onclick = snap;
document.addEventListener('keydown', e => { if (e.code === 'Space') { e.preventDefault(); snap(); } });
</script>
</body>
</html>
""".encode("utf-8")


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass  # не засоряем консоль логом каждого запроса

        def log_message(self, fmt, *args):
            pass          # не сорим в консоль запросами браузера

        def handle_one_request(self):
            # Закрытая вкладка — это не ошибка программы. Windows при этом
            # кидает ConnectionAbortedError (WinError 10053), Linux —
            # BrokenPipeError. Гасим все три, иначе socketserver печатает
            # простыню трассировки поверх наших цифр.
            try:
                BaseHTTPRequestHandler.handle_one_request(self)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                self.close_connection = True

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(PAGE)))
                self.end_headers()
                self.wfile.write(PAGE)
            elif self.path == "/quit":
                # 07.10: штатная остановка (закрыть запись видео с индексом), не kill.
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")
                if state.recorder is not None:
                    state.recorder.close()
                print("Остановлено по /quit")
                sys.stdout.flush()
                os._exit(0)
            elif self.path == "/clock":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(CLOCK_PAGE)))
                self.end_headers()
                self.wfile.write(CLOCK_PAGE)
            elif self.path == "/metrics":
                body = json.dumps(state.metrics()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/airlog":
                body = json.dumps(state.airlog.snapshot(), ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/stream.mjpg":
                self.stream()
            else:
                self.send_error(404)

        def stream(self):
            self.send_response(200)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Type",
                             "multipart/x-mixed-replace; boundary=halowframe")
            self.end_headers()
            seq = -1
            try:
                while True:
                    jpeg, seq = state.wait_frame(seq)
                    if jpeg is None:
                        continue
                    self.wfile.write(b"--halowframe\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(b"Content-Length: %d\r\n\r\n" % len(jpeg))
                    self.wfile.write(jpeg)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # вкладку закрыли или обновили — это нормально

    return Handler


def udp_loop(state, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
    sock.bind(("", port))
    print("Слушаю UDP :%d" % port)
    while True:
        data, _ = sock.recvfrom(2048)
        state.on_packet(data)


def open_serial_quiet(port, baud, timeout):
    """Открыть порт, НЕ дёргая линии DTR/RTS.

    25.08. Раньше здесь было `serial.Serial(port, ...)`, а линии гасились уже
    после открытия. Поздно: pyserial поднимает их в момент открытия, и плата
    успевает перезагрузиться. На приёмнике это смертельно — его модуль в
    прозрачном режиме не принимает новые подключения, поэтому перезагрузка
    ESP32 рвёт связь насовсем, до холодного старта обеих плат. Ровно так
    подключение просмотрщика убивало уже работающий поток.

    Настройки применяются в момент открытия, поэтому выставляем их заранее.
    """
    import serial          # как и в остальных местах файла — импорт по месту,
                           # чтобы просмотрщик работал и без pyserial (UDP-путь)
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = timeout
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser


def serial_loop(state, port, baud):
    try:
        import serial  # pyserial, ставится отдельно: pip install pyserial
    except ImportError:
        print("pyserial не установлен, RSSI со стороны AP показан не будет "
              "(pip install pyserial)")
        return

    while True:
        try:
            with open_serial_quiet(port, baud, 2) as ser:
                print("Читаю метрики AP из %s" % port)
                while True:
                    line = ser.readline().decode("utf-8", "ignore").strip()
                    if not line.startswith("{"):
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("role") != "ap":
                        continue
                    with state.lock:
                        state.ap_conn = bool(msg.get("conn"))
                        rssi = msg.get("rssi")
                        state.ap_rssi = rssi if rssi else None
        except Exception as e:
            print("Serial %s: %s — повтор через 3 с" % (port, e))
            time.sleep(3)


def _apply_meta(state, payload):
    """Разбирает запись 'M' (метрики приёмника) и кладёт их в state."""
    try:
        msg = json.loads(payload.decode("utf-8", "ignore"))
    except json.JSONDecodeError:
        return
    if msg.get("role") != "ap":
        return
    with state.lock:
        state.ap_conn = bool(msg.get("conn"))
        rssi = msg.get("rssi")
        state.ap_rssi = rssi if rssi else None
        # Поля прошивки шага 3 (прозрачный режим). На старой прошивке их нет —
        # get вернёт None, и в CSV будет пусто.
        state.ap_ok = msg.get("ok")
        state.ap_crc_err = msg.get("crc_err")
        state.ap_len_err = msg.get("len_err")
        state.ap_junk = msg.get("junk")
        state.ap_fwd = msg.get("fwd")
        # 24.09: сбои UART на приёме. На прошивках до 24.09 ключей нет — будет пусто.
        state.ap_u_ovf = msg.get("u_ovf")
        state.ap_u_bfull = msg.get("u_bfull")
        state.ap_u_frame = msg.get("u_frame")
        state.ap_u_brk = msg.get("u_brk")
        # -32768 в прошивке означает "команда осталась без ответа".
        margin = msg.get("margin")
        bgr = msg.get("bgr")
        state.ap_margin = None if margin in (None, -32768) else margin
        state.ap_bgr = None if bgr in (None, -32768) else bgr


def crc16(data):
    """CRC16-CCITT, та же, что в lib/HalowVideo/halow_stream.h."""
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _drain_usb(buf, state):
    """
    Вытаскивает из буфера все целые записи AP-USB-потока. Оставляет хвост.

    Запись: [0xA5][0x5A][type][len_lo][len_hi][crc_lo][crc_hi][payload].
    CRC добавлена 15.08: USB CDC на плате теряет байты под нагрузкой, и без
    проверки такая запись доезжала сдвинутой — в картинке это выглядело как
    радужный шум при сохранной геометрии. Теперь битые записи считаются и
    выбрасываются.
    """
    while True:
        i = buf.find(USB_SYNC)
        if i < 0:
            # Синхромаркера нет: держим последний байт (вдруг это первая
            # половинка 0xA5, а 0x5A придёт следующим чтением).
            if len(buf) > 1:
                state.apcon.feed(bytes(buf[:-1]))
                del buf[:-1]
            return
        if i > 0:
            state.apcon.feed(bytes(buf[:i]))  # текст приёмника до маркера
            del buf[:i]
        if len(buf) < 7:
            return                            # ждём type + длину + crc
        typ = buf[2]
        length = buf[3] | (buf[4] << 8)
        want_crc = buf[5] | (buf[6] << 8)
        if len(buf) < 7 + length:
            return                            # ждём весь payload
        payload = bytes(buf[7:7 + length])

        if crc16(payload) != want_crc:
            # Байты потерялись по дороге. Сдвигаем на два байта и ищем
            # следующий маркер: выбросить всю запись нельзя, её длина тоже
            # могла приехать испорченной.
            with state.lock:
                state.usb_crc_err += 1
            del buf[:2]
            continue

        del buf[:7 + length]
        if typ == USB_TYPE_VIDEO:
            state.on_packet(payload)          # payload = app_hdr + кусок JPEG
        elif typ == USB_TYPE_META:
            _apply_meta(state, payload)
        elif typ == USB_TYPE_LOG:
            state.airlog.on_packet(payload)
        # чужой type — просто пропускаем, ресинк по следующему маркеру


def serial_video_loop(state, port, baud):
    """Читает видео и метрики из USB приёмника (HalowVideo_AP)."""
    try:
        import serial  # pyserial: pip install pyserial
    except ImportError:
        print("pyserial не установлен — режим --serial-video недоступен "
              "(pip install pyserial)")
        return

    while True:
        try:
            with open_serial_quiet(port, baud, 1) as ser:
                print("Читаю видео+метрики приёмника из %s" % port)
                buf = bytearray()
                while True:
                    chunk = ser.read(4096)
                    if chunk:
                        buf.extend(chunk)
                        _drain_usb(buf, state)
        except Exception as e:
            print("Serial %s: %s — повтор через 3 с" % (port, e))
            time.sleep(3)


CSV_COLUMNS = [
    "t_iso",            # время по часам ПК
    "t_s",              # секунд от первого коннекта плат
    "note",             # метка прогона (--note или введённая с клавиатуры)
    "marker",           # непусто в той строке, где метку сменили с клавиатуры

    # Скользящее окно 5 с — то же, что видно на веб-странице. Для глаза.
    "fps_win", "kbps_win",

    # За интервал строки. Для расчётов: усреднять и считать доверительные
    # интервалы надо по ним, а не по сглаженному окну.
    "frames_d", "frames_lost_d", "bytes_d", "kbps_i",

    # Накопленные итоги с начала прогона.
    "frames_ok", "frames_lost", "chunks_rx", "chunks_exp", "chunk_loss_pct",
    "bytes_total",

    "frame_bytes", "resolution",
    "sta_rssi", "ap_rssi", "ap_conn",

    # Счётчики приёмника. На прошивке шага 3 crc_err — главный индикатор:
    # растёт => байты теряются между ESP32 и модулем или в эфире.
    "ap_ok", "ap_crc_err", "ap_len_err", "ap_junk", "ap_fwd",
    "ap_crc_err_d", "ap_junk_d",

    # 24.09: сбои UART на приёме ESP32 приёмника. u_ovf — аппаратный FIFO
    # переполнен (задержка прерывания), u_bfull — кольцо 16 КБ полно,
    # u_frame — ошибка стопового бита (уровень битов), u_brk — линия в нуле.
    "ap_u_ovf", "ap_u_bfull", "ap_u_frame", "ap_u_brk",

    # Порог занятости канала на приёмнике: запас в дБ и измеренный фоновый
    # уровень. Пусто => команда осталась без ответа, то есть модуль к моменту
    # старта скетча уже не был в AT-режиме и настройка НЕ применилась.
    "ap_margin", "ap_bgr",

    # Битые записи на USB между приёмником и ПК. Растёт => байты теряет USB,
    # а не радио.
    "usb_crc_err", "usb_crc_err_d",

    # Кадры, собравшиеся целиком, но не сошедшиеся по CRC всего JPEG.
    "frame_crc_err", "frame_crc_err_d",

    # 07.10, гибрид FEC + повтор. useful — байты JPEG ПОКАЗАННЫХ кадров: в
    # kbps_* входят и контрольные куски, и повторы, и куски потерянных кадров.
    # fec_m — контрольных в последнем кадре; sta_rssi в опыте HARQ_AB_MS — номер этапа.
    "useful_kbps_win", "useful_kbps_i", "useful_total", "fec_m",
    "fec_saved", "fec_saved_d", "fec_chunks", "resend_saved", "resend_saved_d",
    "resend_rx", "parity_rx", "frames_late", "frames_late_d", "dup_rx",
]


class CsvLogger(threading.Thread):
    """
    Пишет метрики в CSV, по строке на интервал.

    Файл создаётся НЕ при запуске программы, а в момент первого принятого
    пакета — то есть при первом коннекте плат. Так в логе не остаётся десяти
    минут нулей, пока оператор идёт с платой на позицию, и t_s=0 означает
    именно начало передачи.

    Каждая строка сбрасывается на диск сразу: полевой тест может кончиться
    севшим аккумулятором, и терять из-за этого весь прогон не хочется.
    """

    def __init__(self, state, path=None, interval=1.0, note=""):
        super().__init__(daemon=True)
        self.state = state
        self.path = path
        self.interval = max(0.2, interval)
        self.note = note
        self.marker = ""
        self.lock = threading.Lock()
        self.rows = 0

    def set_note(self, text):
        """Сменить метку прогона на ходу (ввод с клавиатуры)."""
        with self.lock:
            self.note = text
            self.marker = text

    def _open(self, t0):
        path = self.path
        if not path:
            stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(t0))
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.note)
            name = "halow_%s%s.csv" % (stamp, ("_" + safe) if safe else "")
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", name)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        f = open(path, "w", newline="", encoding="utf-8")
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        f.flush()
        print("CSV: пишу в %s" % path)
        return f, w

    def run(self):
        # Ждём первый пакет — это и есть "первый коннект плат".
        while True:
            t0 = self.state.totals()["first_packet_at"]
            if t0 is not None:
                break
            time.sleep(0.1)

        f, writer = self._open(t0)
        prev = self.state.totals()
        prev_t = t0
        next_tick = time.time() + self.interval

        try:
            while True:
                time.sleep(max(0.0, next_tick - time.time()))
                next_tick += self.interval

                now = time.time()
                cur = self.state.totals()
                m = self.state.metrics()
                dt = max(1e-6, now - prev_t)

                with self.lock:
                    note, marker = self.note, self.marker
                    self.marker = ""

                bytes_d = cur["bytes_total"] - prev["bytes_total"]
                loss = 0.0
                if cur["chunks_expected"]:
                    loss = max(0.0, 100.0 * (1 - cur["chunks_rx"] / cur["chunks_expected"]))

                try:
                    row = {
                        "t_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
                        "t_s": round(now - t0, 2),
                        "note": note,
                        "marker": marker,
                        "fps_win": m["fps"],
                        "kbps_win": m["kbps"],
                        "frames_d": cur["frames_ok"] - prev["frames_ok"],
                        "frames_lost_d": cur["frames_lost"] - prev["frames_lost"],
                        "bytes_d": bytes_d,
                        "kbps_i": round(bytes_d * 8 / dt / 1000.0, 1),
                        "frames_ok": cur["frames_ok"],
                        "frames_lost": cur["frames_lost"],
                        "chunks_rx": cur["chunks_rx"],
                        "chunks_exp": cur["chunks_expected"],
                        "chunk_loss_pct": round(loss, 2),
                        "bytes_total": cur["bytes_total"],
                        "frame_bytes": cur["frame_bytes"],
                        "resolution": cur["resolution"],
                        "sta_rssi": cur["sta_rssi"],
                        "ap_rssi": cur["ap_rssi"],
                        "ap_conn": "" if cur["ap_conn"] is None else int(bool(cur["ap_conn"])),
                        "ap_ok": cur["ap_ok"],
                        "ap_crc_err": cur["ap_crc_err"],
                        "ap_len_err": cur["ap_len_err"],
                        "ap_junk": cur["ap_junk"],
                        "ap_fwd": cur["ap_fwd"],
                        "ap_u_ovf": cur.get("ap_u_ovf"),
                        "ap_u_bfull": cur.get("ap_u_bfull"),
                        "ap_u_frame": cur.get("ap_u_frame"),
                        "ap_u_brk": cur.get("ap_u_brk"),
                        "ap_margin": cur.get("ap_margin"),
                        "ap_bgr": cur.get("ap_bgr"),
                        "ap_crc_err_d": _delta(cur["ap_crc_err"], prev["ap_crc_err"]),
                        "ap_junk_d": _delta(cur["ap_junk"], prev["ap_junk"]),
                        "usb_crc_err": cur.get("usb_crc_err", 0),
                        "usb_crc_err_d": _delta(cur.get("usb_crc_err", 0), prev.get("usb_crc_err", 0)),
                        "frame_crc_err": cur.get("frame_crc_err", 0),
                        "frame_crc_err_d": _delta(cur.get("frame_crc_err", 0), prev.get("frame_crc_err", 0)),
                        "useful_kbps_win": m["useful_kbps"],
                        "useful_kbps_i": round((cur["useful_total"] - prev["useful_total"]) * 8 / dt / 1000.0, 1),
                        "useful_total": cur["useful_total"],
                        "fec_m": cur["fec_m"],
                        "fec_saved": cur["fec_saved"],
                        "fec_saved_d": cur["fec_saved"] - prev["fec_saved"],
                        "fec_chunks": cur["fec_chunks"],
                        "resend_saved": cur["resend_saved"],
                        "resend_saved_d": cur["resend_saved"] - prev["resend_saved"],
                        "resend_rx": cur["resend_rx"],
                        "parity_rx": cur["parity_rx"],
                        "frames_late": cur["frames_late"],
                        "frames_late_d": cur["frames_late"] - prev["frames_late"],
                        "dup_rx": cur["dup_rx"],
                    }
                    writer.writerow(row)
                    f.flush()
                    self.rows += 1
                except Exception as e:
                    # Раньше исключение здесь тихо убивало поток, и в файле
                    # оставался один заголовок. Лучше шумно, чем незаметно.
                    print("CSV: ошибка записи строки: %r" % e)

                prev, prev_t = cur, now
        finally:
            f.close()


def _delta(cur, prev):
    """Разность счётчиков, которых может не быть на старой прошивке."""
    if cur is None or prev is None:
        return ""
    return cur - prev


def note_input_loop(logger):
    """
    Ввод меток с клавиатуры прямо во время прогона.

    В полевом тесте это главное удобство: отошёл на 50 метров — набрал "50m"
    и Enter. Метка попадёт в столбец marker той строки и станет note для всех
    следующих, так что потом прогон режется на участки одним фильтром.
    """
    for line in sys.stdin:
        text = line.strip()
        if text:
            logger.set_note(text)
            print("метка: %s" % text)


def main():
    ap = argparse.ArgumentParser(description="Просмотрщик видео T-Halow")
    ap.add_argument("--udp-port", type=int, default=5000,
                    help="UDP-порт, куда шлёт камера (по умолчанию 5000)")
    ap.add_argument("--http-port", type=int, default=8099,
                    help="порт веб-страницы (по умолчанию 8099)")
    ap.add_argument("--serial-video", metavar="PORT",
                    help="COM-порт приёмника (HalowVideo_AP): видео + метрики из USB "
                         "(рабочий путь, например COM7)")
    ap.add_argument("--serial", metavar="PORT",
                    help="устар.: COM-порт платы AP только для RSSI (текстовый JSON)")
    ap.add_argument("--serial-baud", type=int, default=115200)
    ap.add_argument("--csv", nargs="?", const="", metavar="ФАЙЛ",
                    help="писать метрики в CSV. Файл создаётся при первом принятом "
                         "пакете (первый коннект плат). Без значения имя будет "
                         "tools/logs/halow_ДАТА_ВРЕМЯ[_note].csv")
    ap.add_argument("--csv-interval", type=float, default=1.0,
                    help="секунд на строку CSV (по умолчанию 1.0)")
    ap.add_argument("--note", default="",
                    help="метка прогона: дистанция, MCS, что меняли. Попадает в "
                         "имя файла и в столбец note")
    ap.add_argument("--playout-ms", type=int, default=0,
                    help="07.10, гибрид: сколько собранный кадр ждёт более старый "
                         "недособранный (его могут дослать повтором). 0 — показывать "
                         "сразу; с повтором камеры имеет смысл ~700")
    ap.add_argument("--no-http", action="store_true",
                    help="не поднимать веб-страницу — режим чистого логгера")
    ap.add_argument("--no-record", action="store_true",
                    help="не писать видео в файл (по умолчанию пишется само: файл AVI на "
                         "каждый сеанс связи в logs/video)")
    args = ap.parse_args()

    state = State()
    if not args.no_record:
        state.recorder = AviRecorder(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "video"), args.note)
    state.playout_s = max(0, args.playout_ms) / 1000.0
    state.airlog.note = args.note
    state.apcon.note = args.note

    # UDP слушаем всегда — он не мешает, а вдруг мост модуля заработает.
    threading.Thread(target=udp_loop, args=(state, args.udp_port), daemon=True).start()
    if args.serial_video:
        threading.Thread(target=serial_video_loop,
                         args=(state, args.serial_video, args.serial_baud),
                         daemon=True).start()
    if args.serial:
        threading.Thread(target=serial_loop,
                         args=(state, args.serial, args.serial_baud),
                         daemon=True).start()

    logger = None
    if args.csv is not None:
        logger = CsvLogger(state, path=args.csv or None,
                           interval=args.csv_interval, note=args.note)
        logger.start()
        print("Жду первого пакета — CSV создам, когда платы свяжутся.")
        print("Можно вводить метки: наберите текст и Enter (например 50m).")
        threading.Thread(target=note_input_loop, args=(logger,), daemon=True).start()

    try:
        if args.no_http:
            if logger is None:
                print("--no-http без --csv ничего не делает")
                return
            while True:
                time.sleep(1)
        else:
            server = ThreadingHTTPServer(("0.0.0.0", args.http_port), make_handler(state))
            server.daemon_threads = True
            print("Открывайте http://localhost:%d" % args.http_port)
            server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено")
    finally:
        if state.recorder is not None:
            state.recorder.close()
        if logger is not None:
            t = state.totals()
            print("CSV: строк записано %d" % logger.rows)
            if t["frames_ok"] or t["frames_lost"]:
                total = t["frames_ok"] + t["frames_lost"]
                print("Итог: кадров собрано %d, потеряно %d (%.1f%%), принято %d КБ"
                      % (t["frames_ok"], t["frames_lost"],
                         100.0 * t["frames_lost"] / total if total else 0.0,
                         t["bytes_total"] // 1024))
                print("Гибрид: спас FEC %d кадров (%d кусков), повтор %d кадров, "
                      "опоздали к показу %d, полезных %d КБ"
                      % (t["fec_saved"], t["fec_chunks"], t["resend_saved"],
                         t["frames_late"], t["useful_total"] // 1024))


if __name__ == "__main__":
    main()
