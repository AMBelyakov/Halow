#!/usr/bin/env python3
"""
Опыт эквивалентного затухания: граница связи Wi-Fi HaLow и Wi-Fi 2,4 ГГц без выезда на трассу
(15.10.2026).

ЗАЧЕМ. Полевой замер дальности сорван погодой (дожди, влажность — платы не выдержат). Связь
работает или нет в зависимости только от того, насколько сигнал на входе приёмника выше шума,
а сигнал определяется мощностью и потерями трассы — неважно, набраны эти потери километром
поля или стенами здания. Поэтому граница ищется не в метрах, а в децибелах: в здании
измеряются потери и отношение сигнал/шум, по всем точкам находится наименьшее отношение
сигнал/шум, при котором видео ещё проходит, отсюда — допустимые потери при разрешённой
мощности, и они переводятся в дальность теми же моделями, что в таблице 3.8 записки
(свободное пространство, двухлучевая модель для антенн 1,5/1,5 м и 1,5/50 м).

ДВЕ СЕРИИ НА ОДНИХ И ТЕХ ЖЕ ШЕСТИ ТОЧКАХ — оба конца на разрешённом потолке
  halow — релиз 08.10 на обеих платах: камера с регулятором до 14 дБм (вблизи сама убавляет,
          к краю выходит на потолок — так она работает и на борту), приёмник всегда 14 дБм.
  wifi  — камера examples/WifiVideoTest_CAM_range и приёмник WifiVideoTest_RX_range, оба 20 дБм.
  Пересчёта по мощности нет: край меряется на той мощности, на которой система работает.
  Затухание до края набирается этажами (15.10: доступно 15 этажей): HaLow нужно ≈ 110 дБ,
  Wi-Fi ≈ 105 дБ при 54 и 88 дБ на опорной точке 5 м.
Точки размечаются один раз (скотч на полу) и проходятся обеими сериями.

КАК СЧИТАЕТСЯ
  Потери трассы вместе с антеннами плат: L = P_приёмника − air_rssi (HaLow 14, Wi-Fi 20 дБм;
  камера печатает уровень, с которым его слышит; трасса взаимна). SNR видеопотока (камера →
  приёмник): HaLow — tx_snr из модуля; Wi-Fi — pwr_dbm − L − фон (cam_nf у камеры).
  SNR_мин — нижний 1-дБ интервал SNR, где теряется не больше --loss-ok % видеокадров.
  Допустимые потери при мощности P: L_доп = L + (SNR + P − pwr_dbm − SNR_мин) − 10 дБ запаса.
  Дальность — обращение модели потерь при L_доп.

ЗАПУСК
    python tools/range_eq.py run --tech halow --port COM7     # шесть опытов по 5 мин
    python tools/range_eq.py run --tech wifi  --port COM7
    python tools/range_eq.py run --tech halow --port COM7 --start 4   # продолжить с опыта 4
    python tools/range_eq.py run --tech halow --port COM7 --only 6    # переснять один опыт
    python tools/range_eq.py analyze --tech halow          # пересчёт последней серии
    python tools/range_eq.py compare                       # HaLow и Wi-Fi рядом
"""

import argparse
import csv
import glob
import json
import math
import os
import signal
import statistics
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGDIR = os.path.join(ROOT, "tools", "logs")
VIEWER = os.path.join(ROOT, "tools", "halow_viewer.py")

MARGIN_DB = 10                   # запас на замирания, как в подразделе 3.6
SKIP_S = 30                      # начало прогона не считаем: подключение и разгон
LOSS_OK_PCT = 10                 # видео «проходит», если теряется не больше, %

TECH = {
    "halow": dict(name="Wi-Fi HaLow", f=867.0, proj=14, p_cam=14, p_rx=14,
                  cam="релиз HalowVideoP2P_STA (регулятор до 14 дБм)",
                  rx="HalowVideoP2P_AP (релиз)", noise=-101,
                  table38=(4.90, 0.36, 2.06)),
    "wifi": dict(name="Wi-Fi 2,4 ГГц", f=2437.0, proj=20, p_cam=20, p_rx=20,
                 cam="WifiVideoTest_CAM_range (20 дБм)",
                 rx="WifiVideoTest_RX_range (20 дБм)", noise=-91,
                 table38=(2.58, 0.43, 2.51)),
}

# Шесть точек: (номер, описание, стен на трассе, ожидаемые потери HaLow, дБ). Перекрытие этажа
# оценено грубо в ~10 дБ; на месте ориентироваться на SNR в окне просмотра. Потери Wi-Fi
# ожидаются от замера 13.10 (88 дБ на опорной точке) плюс тот же рост и по 6 дБ сверх HaLow на
# каждую дополнительную стену (3GPP TR 38.901: 8,5 против 14,8 дБ); Wi-Fi кончится раньше.
POINTS = [
    (1, "опорная: приёмник в 5 м от камеры за 1 стеной (как все прежние опыты)", 1, 54),
    (2, "тот же этаж, 10–15 м от камеры, 2 стены", 2, 70),
    (3, "тот же этаж, 30–40 м, 3 стены или за углом коридора", 3, 88),
    (4, "этаж выше (или ниже), над/под камерой", 3, 98),
    (5, "через 2–3 этажа", 3, 108),
    (6, "КРАЙ — своя точка у каждой технологии: уходить, пока видео не начнёт рваться "
        "(потери 10–30 %), и снимать там", 3, 114),
]


def expected(tech, walls, l_halow):
    if tech == "halow":
        return l_halow
    return 88 + (l_halow - 54) + 6.3 * (walls - 1)    # 88 дБ — опорная точка Wi-Fi, 13.10


# ------------------------------------------------------------------ модели потерь
def fspl(d_m, f):
    """Потери в свободном пространстве, дБ (f — МГц)."""
    return 32.44 + 20 * math.log10(f) + 20 * math.log10(d_m / 1000)


def fspl_inv(L, f):
    """Расстояние (м), на котором потери в свободном пространстве равны L."""
    return 1000 * 10 ** ((L - 32.44 - 20 * math.log10(f)) / 20)


def two_ray_inv(L, f, h1, h2):
    """Обращение двухсегментной модели: до излома — свободное пространство, после — 40 дБ/дек."""
    d_bp = 4 * h1 * h2 / (299.792458 / f)
    if L <= fspl(d_bp, f):
        return fspl_inv(L, f)
    return d_bp * 10 ** ((L - fspl(d_bp, f)) / 40)


# ------------------------------------------------------------------ чтение CSV
def num(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def load(path, skip_s=SKIP_S):
    with open(path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if (num(r.get("t_s")) or 0) >= skip_s]


def med(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def row_snr(tech, r, noise):
    """SNR видеопотока камера → приёмник в одной строке CSV."""
    if tech == "halow":
        return num(r.get("tx_snr"))
    rssi, pwr = num(r.get("air_rssi")), num(r.get("pwr_dbm"))
    nf = num(r.get("cam_nf")) or noise
    if None in (rssi, pwr) or not rssi:
        return None
    return pwr - (TECH[tech]["p_rx"] - rssi) - nf


def summarize(tech, rows, noise_default):
    nf = med([num(r.get("cam_nf")) or None for r in rows]) if tech == "wifi" else None
    noise = nf or noise_default
    rssi = med([num(r.get("air_rssi")) or None for r in rows])
    s = dict(n=len(rows), rssi=rssi,
             snr=med([row_snr(tech, r, noise) for r in rows]),
             pwr=med([num(r.get("pwr_dbm")) for r in rows]),
             kbps=med([num(r.get("useful_kbps_i")) for r in rows]))
    fr = sum(num(r.get("frames_d")) or 0 for r in rows)
    fl = sum(num(r.get("frames_lost_d")) or 0 for r in rows)
    s["loss_pct"] = 100 * fl / (fr + fl) if fr + fl else None
    s["L"] = TECH[tech]["p_rx"] - rssi if rssi is not None else None
    s["d_eq"] = fspl_inv(s["L"], TECH[tech]["f"]) if s["L"] is not None else None
    s["noise"] = (s["pwr"] - s["L"] - s["snr"]) if None not in (s["pwr"], s["L"], s["snr"]) else None
    return s


def snr_min_from_data(tech, rows, noise, loss_ok, min_seconds=20):
    """Наименьший 1-дБ интервал SNR, где видео ещё проходит (потери ≤ loss_ok %)."""
    bins = {}
    for r in rows:
        snr = row_snr(tech, r, noise)
        if snr is None:
            continue
        b = bins.setdefault(int(math.floor(snr)), [0, 0, 0])
        b[0] += num(r.get("frames_d")) or 0
        b[1] += num(r.get("frames_lost_d")) or 0
        b[2] += 1
    ok = [k for k, (fr, fl, n) in bins.items()
          if n >= min_seconds and fr + fl and 100 * fl / (fr + fl) <= loss_ok]
    return (min(ok) if ok else None), bins


# ------------------------------------------------------------------ серии
def latest_series(tech):
    dirs = sorted(glob.glob(os.path.join(LOGDIR, f"range_eq_{tech}_*")))
    return dirs[-1] if dirs else None


def load_session(d):
    try:
        with open(os.path.join(d, "session.json"), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"runs": {}}


def save_session(d, sess):
    with open(os.path.join(d, "session.json"), "w", encoding="utf-8") as f:
        json.dump(sess, f, ensure_ascii=False, indent=1)


def fmt(v, nd=0):
    return "—" if v is None else f"{v:.{nd}f}".replace(".", ",")


def quick_report(s):
    return (f"  {s['n']} с; уровень {fmt(s['rssi'])} дБм, потери L = {fmt(s['L'])} дБ "
            f"(в свободном пространстве это {fmt(s['d_eq'])} м); SNR {fmt(s['snr'])} дБ при "
            f"{fmt(s['pwr'])} дБм; видео {fmt(s['kbps'])} кбит/с, потеряно "
            f"{fmt(s['loss_pct'], 1)} % видеокадров")


def evaluate(tech, d, power, margin, snr_min_arg, loss_ok):
    """Сводка серии: по точкам, SNR_мин и пересчёт в дальность."""
    t = TECH[tech]
    sess = load_session(d)
    rows_all, res = [], []
    for n, desc, walls, lh in POINTS:
        run = sess["runs"].get(str(n))
        rows = load(os.path.join(d, run["csv"])) if run and run.get("csv") else []
        rows_all += rows
        res.append((n, desc, summarize(tech, rows, t["noise"]) if rows else None))
    noise = med([s["noise"] for _, _, s in res if s]) or t["noise"]
    snr_min, bins = snr_min_from_data(tech, rows_all, noise, loss_ok)
    if snr_min_arg is not None:
        snr_min = snr_min_arg
    proj, best = {}, None
    for n, desc, s in res:
        if s is None or None in (s["L"], s["snr"], s["pwr"]) or snr_min is None:
            continue
        l_allow = s["L"] + (s["snr"] + power - s["pwr"] - snr_min) - margin
        r = (fspl_inv(l_allow, t["f"]) / 1000, two_ray_inv(l_allow, t["f"], 1.5, 1.5) / 1000,
             two_ray_inv(l_allow, t["f"], 1.5, 50) / 1000)
        proj[n] = (l_allow, r)
        if best is None or s["snr"] < res[best - 1][2]["snr"]:
            best = n                  # ближайшая к краю точка — меньше всего экстраполяции
    return dict(res=res, snr_min=snr_min, bins=bins, proj=proj, best=best)


def cmd_analyze(a):
    t = TECH[a.tech]
    d = a.dir or latest_series(a.tech)
    if not d:
        sys.exit(f"Серий {a.tech} нет: сначала range_eq.py run --tech {a.tech}")
    power = a.power if a.power is not None else t["proj"]
    ev = evaluate(a.tech, d, power, a.margin, a.snr_min, a.loss_ok)
    out = [f"# {t['name']}: эквивалентное затухание — {os.path.basename(d)}", "",
           f"L = {t['p_rx']} дБм (мощность приёмника) − уровень приёмника у камеры. SNR_мин = {fmt(ev['snr_min'])} дБ "
           f"(теряется не больше {a.loss_ok} % видеокадров). Пересчёт — на {power} дБм, "
           f"{t['f']:.0f} МГц, запас {a.margin} дБ.", "",
           "| № | Точка | с | Уровень, дБм | L, дБ | Своб. простр., м | SNR, дБ | Фон, дБм | "
           "Видео, кбит/с | Потери видеокадров, % |", "|---|---|---|---|---|---|---|---|---|---|"]
    for n, desc, s in ev["res"]:
        if s is None:
            out.append(f"| {n} | {desc} | — | нет связи | | | | | | |")
            continue
        out.append(f"| {n} | {desc} | {s['n']} | {fmt(s['rssi'])} | {fmt(s['L'])} | "
                   f"{fmt(s['d_eq'])} | {fmt(s['snr'])} | {fmt(s['noise'])} | {fmt(s['kbps'])} | "
                   f"{fmt(s['loss_pct'], 1)} |")
    out += ["", "## Пересчёт в дальность", "",
            f"| № | L_доп при {power} дБм, дБ | Своб. простр., км | Антенны 1,5/1,5 м, км | "
            "1,5/50 м, км |", "|---|---|---|---|---|"]
    for n, (l_allow, r) in sorted(ev["proj"].items()):
        out.append(f"| {n} | {fmt(l_allow)} | {fmt(r[0], 2)} | {fmt(r[1], 2)} | {fmt(r[2], 2)} |")
    if ev["best"]:
        l_allow, r = ev["proj"][ev["best"]]
        ref = t["table38"]
        out += ["", f"Итог по точке, ближайшей к краю (опыт {ev['best']}): допустимые потери "
                f"{fmt(l_allow)} дБ; дальность {fmt(r[0], 2)} км в свободном пространстве, "
                f"{fmt(r[1], 2)} км с антеннами у земли, {fmt(r[2], 2)} км с антенной на борту "
                f"50 м. Расчёт по паспорту (табл. 3.8): {fmt(ref[0], 2)} / {fmt(ref[1], 2)} / "
                f"{fmt(ref[2], 2)} км."]
    out += ["", "## Видео по интервалам SNR (все опыты серии)", "",
            "| SNR, дБ | с | Потери видеокадров, % |", "|---|---|---|"]
    for k in sorted(ev["bins"]):
        fr, fl, nsec = ev["bins"][k]
        out.append(f"| {k}…{k + 1} | {nsec} | {fmt(100 * fl / (fr + fl), 1) if fr + fl else '—'} |")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(d, "report.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"\nОтчёт: {os.path.join(d, 'report.md')}")


def cmd_compare(a):
    ds = {k: latest_series(k) for k in TECH}
    if not all(ds.values()):
        sys.exit("Для сравнения нужны обе серии: run --tech halow и run --tech wifi")
    ev = {k: evaluate(k, ds[k], TECH[k]["proj"], a.margin, None, a.loss_ok) for k in TECH}
    out = ["# Wi-Fi HaLow и Wi-Fi 2,4 ГГц на одних и тех же точках", "",
           "| № | Точка | L HaLow, дБ | L Wi-Fi, дБ | Разница, дБ | Видео HaLow / Wi-Fi, кбит/с |",
           "|---|---|---|---|---|---|"]
    for i, (n, desc, _, _) in enumerate(POINTS):
        h, w = ev["halow"]["res"][i][2], ev["wifi"]["res"][i][2]
        lh, lw = (h or {}).get("L"), (w or {}).get("L")
        out.append(f"| {n} | {desc} | {fmt(lh)} | {fmt(lw) if w else 'нет связи'} | "
                   f"{fmt(lw - lh) if None not in (lh, lw) else '—'} | "
                   f"{fmt((h or {}).get('kbps'))} / {fmt((w or {}).get('kbps'))} |")
    out += ["", "| Технология | Мощность по нормам РФ, дБм | Своб. простр., км | "
            "Антенны 1,5/1,5 м, км | 1,5/50 м, км |", "|---|---|---|---|---|"]
    for k, t in TECH.items():
        b = ev[k]["best"]
        r = ev[k]["proj"][b][1] if b else (None, None, None)
        out.append(f"| {t['name']} | {t['proj']} | {fmt(r[0], 2)} | {fmt(r[1], 2)} | {fmt(r[2], 2)} |")
    text = "\n".join(out)
    print(text)
    path = os.path.join(LOGDIR, time.strftime("range_eq_compare_%Y%m%d_%H%M.md"))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"\nОтчёт: {path}")


def beep(kind):
    """Звук: 'alarm' — три коротких (обрыв, нет связи), 'done' — длинный (опыт закончен)."""
    try:
        import winsound
        if kind == "alarm":
            for _ in range(3):
                winsound.Beep(1200, 150)
                time.sleep(0.08)
        else:
            winsound.Beep(800, 900)
    except Exception:
        print("\a", end="", flush=True)


def tail(path):
    """Число строк CSV и последняя строка (dict) — для живой строки во время опыта."""
    try:
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except (FileNotFoundError, PermissionError):
        return 0, None
    return len(rows), (rows[-1] if rows else None)


def live_line(tech, r):
    t = TECH[tech]
    rssi = num(r.get("air_rssi"))
    snr = row_snr(tech, r, t["noise"])
    L = t["p_rx"] - rssi if rssi else None
    return (f"SNR {fmt(snr)} дБ, потери {fmt(L)} дБ, видео {fmt(num(r.get('useful_kbps_win')))} кбит/с, "
            f"мощность камеры {fmt(num(r.get('pwr_dbm')))} дБм")


def record(a, path, desc, n):
    """Один опыт: ждёт связь до --link-wait с, затем пишет --duration с от первой строки CSV.
    Живая строка раз в секунду, звук при обрыве и в конце. Ctrl+C — закончить опыт досрочно."""
    cmd = [sys.executable, VIEWER, "--serial-video", a.port, "--csv", path,
           "--note", f"RE-{a.tech}-{n} {desc}"]
    if a.no_http:
        cmd.append("--no-http")
    p = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                         if os.name == "nt" else 0, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    t_start, t_link, last_n, last_grow, alarmed = time.time(), None, 0, time.time(), False
    status = "ok"
    try:
        while p.poll() is None:
            time.sleep(1)
            now = time.time()
            nrows, r = tail(path)
            if t_link is None:
                if nrows:
                    t_link, last_grow = now, now
                elif now - t_start > a.link_wait:
                    print(f"\r    НЕТ СВЯЗИ {a.link_wait} с — край пройден.                       ")
                    beep("alarm")
                    status = "nolink"
                    break
                else:
                    print(f"\r    жду связь… {int(now - t_start)} с  ", end="", flush=True)
                    continue
            if nrows > last_n:
                last_n, last_grow = nrows, now
                if alarmed:
                    print("\n    связь восстановилась")
                    alarmed = False
            lost = now - last_grow > 10 or (r and str(r.get("ap_conn")).lower() not in ("true", "1"))
            if lost and not alarmed:
                print("\n    ОБРЫВ СВЯЗИ — новых данных нет 10 с (опыт продолжается)")
                beep("alarm")
                alarmed = True
            left = int(a.duration - (now - t_link))
            if left <= 0:
                break
            print(f"\r    {left // 60}:{left % 60:02d} | " + (live_line(a.tech, r) if r else "")
                  + "      ", end="", flush=True)
    except KeyboardInterrupt:
        status = "stopped"
        print("\n    опыт остановлен вручную")
    finally:
        if p.poll() is None:
            p.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
    if status != "nolink":
        print("\n    ОПЫТ ЗАВЕРШЁН")
        beep("done")
    return status


def cmd_run(a):
    t = TECH[a.tech]
    d = a.dir or os.path.join(LOGDIR, time.strftime(f"range_eq_{a.tech}_%Y%m%d_%H%M"))
    os.makedirs(d, exist_ok=True)
    sess = load_session(d)
    todo = [p for p in POINTS if (a.only is None or p[0] == a.only) and p[0] >= a.start]
    print(f"{t['name']}. Серия: {d}\nКамера ({t['cam']}) стоит на месте, ходим с ноутбуком и "
          f"приёмником ({t['rx']}).\nОпыт — {a.duration} с от появления связи; первые {SKIP_S} с "
          f"не считаются. Ctrl+C — закончить опыт досрочно.\n")
    skip_to_edge = False
    for n, desc, walls, lh in todo:
        if skip_to_edge and n != POINTS[-1][0]:
            continue
        l_exp = expected(a.tech, walls, lh)
        snr_exp = t["p_cam"] - l_exp - t["noise"]
        print(f"=== Опыт {n} из {len(POINTS)}: {desc}")
        print(f"    ожидаемо: потери ≈ {l_exp:.0f} дБ, SNR ≈ {snr_exp:.0f} дБ"
              + (" — связи может не быть, это тоже результат" if snr_exp < 3 else ""))
        input("    Перейдите с ноутбуком и приёмником на точку и нажмите Enter...")
        path = os.path.join(d, f"re{n}.csv")
        status = record(a, path, desc, n)
        if status == "nolink" or not os.path.exists(path):
            sess["runs"][str(n)] = {"desc": desc, "csv": None}
            save_session(d, sess)
            if n == POINTS[-1][0]:
                continue
            ans = input("    Дальние точки дадут то же. [К] — вернуться ближе и снять КРАЙ (точка "
                        f"{POINTS[-1][0]}), [З] — закончить серию: ").strip().lower()
            if ans in ("з", "z"):
                break
            skip_to_edge = True
            continue
        sess["runs"][str(n)] = {"desc": desc, "csv": os.path.basename(path)}
        save_session(d, sess)
        rows = load(path)
        print((quick_report(summarize(a.tech, rows, t["noise"])) if rows
               else "    после первых 30 с данных нет — связь неустойчива.") + "\n")
    print("Серия записана. Пересчёт:")
    cmd_analyze(argparse.Namespace(tech=a.tech, dir=d, power=a.power, margin=a.margin,
                                   snr_min=a.snr_min, loss_ok=a.loss_ok))


def main():
    ap = argparse.ArgumentParser(description="Опыт эквивалентного затухания (HaLow и Wi-Fi)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "analyze", "compare"):
        p = sub.add_parser(name)
        p.add_argument("--margin", type=float, default=MARGIN_DB, help="запас, дБ (10)")
        p.add_argument("--loss-ok", type=float, default=LOSS_OK_PCT,
                       help="допустимые потери видеокадров для SNR_мин, %% (10)")
        if name == "compare":
            continue
        p.add_argument("--tech", choices=list(TECH), required=True)
        p.add_argument("--power", type=float, default=None,
                       help="мощность для пересчёта, дБм (HaLow 14, Wi-Fi 20)")
        p.add_argument("--snr-min", type=float, default=None,
                       help="задать SNR_мин вручную вместо поиска по данным")
        if name == "run":
            p.add_argument("--port", required=True, help="COM-порт приёмника")
            p.add_argument("--duration", type=int, default=300,
                           help="длина опыта от появления связи, с (300)")
            p.add_argument("--link-wait", type=int, default=90,
                           help="сколько ждать связь, прежде чем признать точку за краем, с (90)")
            p.add_argument("--start", type=int, default=1, help="начать с опыта N")
            p.add_argument("--only", type=int, default=None, help="снять только опыт N")
            p.add_argument("--dir", default=None, help="папка серии (продолжить старую)")
            p.add_argument("--no-http", action="store_true", help="без окна видео в браузере")
        else:
            p.add_argument("dir", nargs="?", default=None, help="папка серии (последняя)")
    a = ap.parse_args()
    {"run": cmd_run, "analyze": cmd_analyze, "compare": cmd_compare}[a.cmd](a)


if __name__ == "__main__":
    main()
