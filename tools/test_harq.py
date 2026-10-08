# -*- coding: utf-8 -*-
"""
Проверка гибрида FEC + повтор без плат (07.10).

Собирает кадры так же, как скетч камеры (куски по P байт, M контрольных:
кусок K+g = XOR кусков i % M == g, дополненных нулями до P), выбрасывает куски
и скармливает пакеты просмотрщику (State.on_packet). Заодно проверяет
логику приёмника (какие пропавшие куски закрываемы — fecRecoverable в скетче
HalowVideoP2P_AP) на тех же наборах потерь.

    python tools/test_harq.py
"""
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import halow_viewer as hv  # noqa: E402

P = 1400


def make_jpeg(n, seed):
    rnd = random.Random(seed)
    body = bytes(rnd.getrandbits(8) for _ in range(n - 4))
    return b"\xff\xd8" + body + b"\xff\xd9"


def packets(fid, jpeg, m, flags_extra=0, only=None):
    """Пакеты кадра в порядке отправки камерой: данные, затем контрольные."""
    k = (len(jpeg) + P - 1) // P
    m = min(m, k)                 # как в камере: групп не больше, чем кусков
    crc = hv.crc16(jpeg)
    mf = m << hv.FEC_M_SHIFT
    out = []
    par = [0] * m
    for i in range(k):
        chunk = jpeg[i * P:(i + 1) * P]
        if m:
            par[i % m] ^= int.from_bytes(chunk, "little")
        fl = mf | (hv.FLAG_LAST if (i + 1 == k and not m) else 0) | flags_extra
        out.append((i, hv.APP_HDR.pack(hv.MAGIC, fid, len(jpeg), i, k, len(chunk), crc, 0, fl) + chunk))
    for g in range(m):
        fl = mf | hv.FLAG_PARITY | (hv.FLAG_LAST if g + 1 == m else 0)
        pay = par[g].to_bytes(P, "little")
        out.append((k + g, hv.APP_HDR.pack(hv.MAGIC, fid, len(jpeg), k + g, k, P, crc, 0, fl) + pay))
    if only is not None:
        out = [x for x in out if x[0] in only]
    return k, out


def resend(fid, jpeg, idxs, m):
    k, pk = packets(fid, jpeg, m, hv.FLAG_RESEND, only=set(idxs))
    return pk


def recoverable(raw, k, m, pmask):
    """Порт fecRecoverable из скетча приёмника."""
    rec = 0
    for g in range(min(m, 16)):
        if not (pmask >> g) & 1:
            continue
        miss = [i for i in range(g, min(k, 64), m) if not (raw >> i) & 1]
        if len(miss) == 1:
            rec |= 1 << miss[0]
    return rec


def feed(st, pk, drop=()):
    raw = pm = 0
    for idx, data in pk:
        if idx in drop:
            continue
        st.on_packet(data)
    return raw, pm


fails = 0


def check(name, cond):
    global fails
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails += 1


# 1. Без потерь, без FEC
st = hv.State()
j = make_jpeg(20000, 1)
k, pk = packets(1, j, 0)
feed(st, pk)
check("целый кадр без FEC показан", st.frames_ok == 1 and st.latest_jpeg == j)

# 2. Пачка из M подряд при M контрольных — закрывается FEC, длина последнего верна
for m in (1, 2, 4, 8):
    st = hv.State()
    j = make_jpeg(20000 + 333 * m, 10 + m)    # последний кусок короче P
    k, pk = packets(5, j, m)
    lost = set(range(k - m, k))               # хвост, включая короткий последний
    feed(st, pk, drop=lost)
    check("M=%d: пачка из %d в хвосте закрыта FEC" % (m, m),
          st.frames_ok == 1 and st.fec_saved == 1 and st.latest_jpeg == j)
    raw = sum(1 << i for i in range(k) if i not in lost)
    rec = recoverable(raw, k, m, (1 << m) - 1)
    check("M=%d: приёмник считает те же куски закрываемыми" % m,
          rec == sum(1 << i for i in lost))

# 3. Пачка M+1 — FEC не закрывает, повтор досылает
st = hv.State()
j = make_jpeg(26000, 3)
k, pk = packets(7, j, 2)
lost = {3, 4, 5}
feed(st, pk, drop=lost)
check("пачка 3 при M=2 не закрыта", st.frames_ok == 0 and len(st.pending) == 1)
raw = sum(1 << i for i in range(k) if i not in lost)
rec = recoverable(raw, k, 2, 0b11)
miss = [i for i in range(k) if not ((raw | rec) >> i) & 1]
check("приёмник: закрыт один из трёх, повторить два", bin(rec).count("1") == 1 and len(miss) == 2)
feed(st, resend(7, j, miss, 2))
check("повтор достроил кадр", st.frames_ok == 1 and st.latest_jpeg == j and st.resend_saved == 1)

# 4. Порядок показа: без ожидания повтор старого кадра опаздывает
st = hv.State()
j1, j2 = make_jpeg(15000, 21), make_jpeg(15000, 22)
_, p1 = packets(10, j1, 0)
_, p2 = packets(11, j2, 0)
feed(st, p1, drop={4})
feed(st, p2)
check("без ожидания: новый кадр показан сразу", st.frames_ok == 1 and st.latest_jpeg == j2)
feed(st, resend(10, j1, [4], 0))
check("без ожидания: дособранный старый не показан (опоздал)",
      st.frames_ok == 1 and st.frames_late == 1 and st.latest_jpeg == j2)

# 5. С ожиданием — оба по порядку
st = hv.State()
st.playout_s = 5.0
feed(st, p1, drop={4})
feed(st, p2)
check("с ожиданием: новый кадр ждёт старый", st.frames_ok == 0 and 11 in st.ready)
feed(st, resend(10, j1, [4], 0))
check("с ожиданием: показаны оба, последним новый",
      st.frames_ok == 2 and st.latest_jpeg == j2 and st.frames_late == 0)

# 6. Ожидание не вечное
st = hv.State()
st.playout_s = 0.05
feed(st, p1, drop={4})
feed(st, p2)
time.sleep(0.06)
st.metrics()
check("с ожиданием: по истечении показан новый без старого", st.frames_ok == 1 and st.latest_jpeg == j2)

# 7. Перезагрузка камеры: номера заново
st = hv.State()
_, pa = packets(500, j1, 0)
_, pb = packets(1, j2, 0)
feed(st, pa)
feed(st, pb)
check("номер с начала после перезагрузки камеры принят", st.frames_ok == 2 and st.latest_jpeg == j2)

# 8. Случайные потери: всё, что восстановимо по правилу групп, собрано верно
rnd = random.Random(7)
bad = 0
for t in range(300):
    m = rnd.choice((0, 1, 2, 3, 4, 6, 8))
    j = make_jpeg(rnd.randint(3000, 60000), 100 + t)
    st = hv.State()
    k, pk = packets(t + 1, j, m)
    drop = {i for i in range(k + m) if rnd.random() < 0.15}
    feed(st, pk, drop=drop)
    raw = sum(1 << i for i in range(k) if i not in drop)
    pmask = sum(1 << g for g in range(m) if (k + g) not in drop)
    rec = recoverable(raw, k, m, pmask)
    full = (raw | rec) == (1 << k) - 1
    shown = st.frames_ok == 1 and st.latest_jpeg == j
    if full != shown or st.frame_crc_err:
        bad += 1
check("300 случайных кадров: просмотрщик и приёмник согласны, CRC без ошибок", bad == 0)

print("ИТОГ: %s" % ("всё прошло" if not fails else "ошибок %d" % fails))
sys.exit(1 if fails else 0)
