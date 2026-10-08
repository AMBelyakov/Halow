# -*- coding: utf-8 -*-
"""Рисунки основной части ВКР (главы 2–3). Запуск: python figures_main.py

Цвета — первые три слота эталонной палитры навыка dataviz (синий, оранжевый,
бирюзовый): они проверены производителем палитры на различимость всех пар, в
том числе при нарушениях цветового зрения. Для чёрно-белой печати каждая серия
дополнительно различается типом линии, а подписи стоят прямо у линий.
"""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

plt.rcParams.update({
    # Times New Roman, а где его нет — метрически совместимый Liberation Serif
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"],
    "font.size": 12,
    "axes.edgecolor": "#52514e",
    "axes.labelcolor": "#0b0b0b",
    "xtick.color": "#52514e",
    "ytick.color": "#52514e",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "savefig.dpi": 200,
})
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#dcdad4"


def fspl_db(d_m, f_mhz):
    """Потери в свободном пространстве, дБ (формула Фрииса в инженерной форме)."""
    return 20 * math.log10(d_m / 1000) + 20 * math.log10(f_mhz) + 32.44


# ------------------------------------------------------------ рисунок 2.1
def stand_scheme(path="fig_stand.png"):
    fig, ax = plt.subplots(figsize=(6.5, 3.9))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")

    def box(x, y, w, h, title, body, accent=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
                                    fc="#eef4fc" if accent else "#f6f5f2",
                                    ec=BLUE if accent else INK2, lw=1.0))
        ax.text(x + w / 2, y + h - 2.6, title, ha="center", va="top", fontsize=10.5,
                weight="bold", color=INK)
        ax.text(x + w / 2, y + h - 7.4, body, ha="center", va="top", fontsize=9, color=INK2,
                linespacing=1.25)

    def arrow(x0, y0, x1, y1, label=None, dy=1.6, style="-|>", ls="-"):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=11,
                                     lw=1.1, color=INK2, linestyle=ls))
        if label:
            ax.text((x0 + x1) / 2, (y0 + y1) / 2 + dy, label, ha="center", va="bottom",
                    fontsize=8.5, color=INK2)

    # верхний ряд — камера (бортовой узел, модуль в режиме точки доступа)
    box(1, 38, 22, 20, "Камера OV5640", "RGB565,\n480 × 320")
    box(35, 38, 30, 20, "ESP32-S3 камеры", "сжатие JPEG (2 ядра),\nфрагменты ≤ 1400 Б,\nFEC и досылка")
    box(77, 38, 22, 20, "Модуль\nTX-AH-R900P", "\n\nточка доступа (AP)", accent=True)
    arrow(23.8, 48, 34.2, 48, "DVP")
    arrow(65.8, 48, 76.2, 48, "UART")
    ax.text(71, 46.2, "3 Мбод", ha="center", va="top", fontsize=8.5, color=INK2)

    # нижний ряд — приёмник (наземный пункт, модуль в режиме станции)
    box(77, 2, 22, 20, "Модуль\nTX-AH-R900P", "\n\nстанция (STA)", accent=True)
    box(35, 2, 30, 20, "ESP32-S3 приёмника", "пересылка фрагментов,\nквитанция на\nкаждый видеокадр")
    box(1, 2, 22, 20, "ПК", "halow_viewer.py:\nсборка, показ\nв браузере, CSV")
    arrow(76.2, 12, 65.8, 12, "UART")
    ax.text(71, 10.2, "3 Мбод", ha="center", va="top", fontsize=8.5, color=INK2)
    arrow(34.2, 12, 23.8, 12, "USB")

    # радиоканал
    ax.add_patch(FancyArrowPatch((86, 37.2), (86, 22.8), arrowstyle="-|>", mutation_scale=12,
                                 lw=1.6, color=BLUE))
    ax.add_patch(FancyArrowPatch((92, 22.8), (92, 37.2), arrowstyle="-|>", mutation_scale=10,
                                 lw=0.9, color=BLUE, linestyle=(0, (3, 2))))
    ax.text(84.2, 30, "видеокадры\nJPEG", ha="right", va="center", fontsize=8.5, color=INK2)
    ax.text(93.8, 30, "квитанции", ha="left", va="center", fontsize=8.5, color=INK2)
    ax.text(50, 31.5, "Wi-Fi HaLow (IEEE 802.11ah)", ha="center", va="center", fontsize=10,
            color=BLUE, style="italic")
    ax.text(50, 27.5, "867 МГц, канал 2 МГц, ≤ 14 дБм", ha="center", va="center", fontsize=9,
            color=BLUE)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------ рисунок 2.2
def path_loss(path="fig_pathloss.png"):
    f = 867.0                                 # МГц: канал 2 МГц на 867,0 МГц
    lam = 299.792458 / f                      # длина волны, м
    h1, h2 = 1.5, 50.0                        # наземная антенна и антенна на борту БПЛА, м
    d_bp = 4 * h1 * h2 / lam
    d_bp_g = 4 * h1 * h1 / lam                # обе антенны на высоте 1,5 м (как в таблице 3.8)
    ds = [10 * 10 ** (i / 100) for i in range(0, 271)]   # 10 м … 5 км, логарифмический шаг

    fs868 = [fspl_db(d, f) for d in ds]
    fs24 = [fspl_db(d, 2437) for d in ds]

    def two_ray(d, b):
        return fspl_db(d, f) if d <= b else fspl_db(b, f) + 40 * math.log10(d / b)

    tworay = [two_ray(d, d_bp) for d in ds]
    tworay_g = [two_ray(d, d_bp_g) for d in ds]

    fig, ax = plt.subplots(figsize=(6.5, 3.9))
    ax.set_xscale("log")
    ax.grid(True, which="major", color=GRID, lw=0.6)
    ax.grid(True, which="minor", axis="x", color=GRID, lw=0.3)
    ax.plot(ds, fs24, color=ORANGE, lw=2, ls="--", label="2437 МГц, свободное пространство")
    ax.plot(ds, fs868, color=BLUE, lw=2, label="867 МГц, свободное пространство")
    # до точки излома двухлучевая модель совпадает со свободным пространством,
    # поэтому рисуется только после неё — иначе она закрывает синюю линию
    tail = [(d, v) for d, v in zip(ds, tworay) if d >= d_bp]
    ax.plot([d for d, _ in tail], [v for _, v in tail], color=AQUA, lw=2, ls="-.",
            label="867 МГц, двухлучевая модель (h₁ = 1,5 м, h₂ = 50 м)")
    tail_g = [(d, v) for d, v in zip(ds, tworay_g) if d >= d_bp_g]
    ax.plot([d for d, _ in tail_g], [v for _, v in tail_g], color=INK2, lw=1.6, ls=":",
            label="867 МГц, двухлучевая модель (h₁ = h₂ = 1,5 м)")
    ax.axvline(d_bp, color=INK2, lw=0.8, ls=":")
    ax.text(d_bp * 1.05, 152, f"точка излома\n{d_bp:.0f} м", fontsize=9, color=INK2, va="top")
    ax.axvline(d_bp_g, color=INK2, lw=0.8, ls=":")
    ax.text(d_bp_g * 1.05, 152, f"точка излома\n{d_bp_g:.0f} м", fontsize=9, color=INK2,
            va="top")
    # прямые подписи — только там, где линии далеко друг от друга
    ax.text(14, fspl_db(14, 2437) + 2.5, "2437 МГц", fontsize=9, color=INK, rotation=13)
    ax.legend(loc="lower right", frameon=False, fontsize=9, handlelength=2.6)
    ax.set_xlim(10, 5000)
    ax.set_ylim(30, 155)
    ax.set_xlabel("Расстояние, м")
    ax.set_ylabel("Потери на трассе, дБ")
    ax.set_xticks([10, 30, 100, 300, 1000, 3000])
    ax.set_xticklabels(["10", "30", "100", "300", "1000", "3000"])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------ рисунок 3.1
# (подпись, кбит/с, группа) — из журнала испытаний docs/halow_link_debug.md и README релиза.
# Группа 0 — лабораторный этап: помещение до 5 м, 240×176, канал 4 МГц на 866 МГц, скорость на приёмнике.
# Группа 1 — трасса 5 м, канал 2 МГц на 867 МГц; мера скорости указана в подписи.
STAGES = [
    ("01.09  230 400 бод, полоса приёма 8 → 4 МГц", 121, 0),
    ("03.09  384 000 бод, пауза 8 мс", 184, 0),
    ("23.09  без отладочного фильтра", 222, 0),
    ("24.09  460 800 бод", 235, 0),
    ("24.09  1 Мбод, кольцо модуля 8 КБ", 368, 0),
    ("25.09  3 Мбод, чтение FIFO в модуле", 523, 0),
    ("25.09  пауза 3 мс, опрос приёма раз в кадр", 708, 0),
    ("29.09  320×240, RTS/CTS заводской (подача)", 282, 1),
    ("29.09  320×240, RTS/CTS выключен (подача)", 618, 1),
    ("06.10  480×320, esp_new_jpeg, ток ×1 (приёмник)", 906, 1),
    ("08.10  итог: граница MCS, FEC и досылка (полезная)", 1063, 1),
]


def throughput_steps(path="fig_throughput.png"):
    st = STAGES[::-1]
    # между группами — пустая строка-разделитель
    ys, labels, vals, cols = [], [], [], []
    y = 0
    prev = st[0][2]
    for lab, v, g in st:
        if g != prev:
            y += 0.8
            prev = g
        ys.append(y)
        labels.append(lab)
        vals.append(v)
        cols.append(BLUE if g == 0 else AQUA)
        y += 1
    fig, ax = plt.subplots(figsize=(6.5, 4.6))
    ax.barh(ys, vals, height=0.62, color=cols)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=9.5)
    for yy, v in zip(ys, vals):
        ax.text(v + 10, yy, f"{v}", va="center", fontsize=10, color=INK)
    n5 = sum(1 for s_ in STAGES if s_[2] == 1)
    ax.text(1180, ys[n5 - 1] + 0.55, "5 м, 867 МГц, канал 2 МГц", ha="right", va="bottom",
            fontsize=9, color=AQUA, weight="bold")
    ax.text(1180, ys[-1] + 0.55, "помещение, до 5 м, 240×176, 866 МГц, канал 4 МГц", ha="right",
            va="bottom", fontsize=9, color=BLUE, weight="bold")
    ax.set_xlim(0, 1200)
    ax.set_ylim(-0.6, ys[-1] + 1.4)
    ax.set_xlabel("Скорость видеопотока, кбит/с")
    ax.grid(True, axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------ сравнение с Wi-Fi и LoRa
# Режимы: (подпись, скорость PHY Мбит/с, ЭИИМ дБм, чувствительность дБм). Расчёт автора:
# свободное пространство / двухлучевая модель, антенны 0 дБи, запас на замирания 10 дБ.
# Wi-Fi HaLow: паспорт TX-AH V6.2 (1 МГц MCS10); 2 МГц — оценка −6 дБ от 8 МГц. ЭИИМ 14 дБм.
# ESP32-S3: паспорт (802.11b 1 Мбит/с, HT20 MCS0, MCS7), ЭИИМ 20 дБм (норма 2,4 ГГц 100 мВт).
# LoRa: Semtech AN1200.22, табл. 1, полоса 125 кГц, SF7…SF12; ЭИМ 25 мВт ≈ 14 дБм (как HaLow).
MARGIN_DB = 10
TECH = [
    ("Wi-Fi HaLow, 867 МГц", 867.0, BLUE, "o", [
        ("1 МГц MCS 10", 0.15, 14, -105.0), ("2 МГц MCS 0*", 0.65, 14, -101.0),
        ("2 МГц MCS 7*", 6.5, 14, -87.0)]),
    ("Wi-Fi 2,4 ГГц (ESP32-S3)", 2437.0, ORANGE, "s", [
        ("802.11b", 1.0, 20, -98.4), ("HT20 MCS 0", 6.5, 20, -92.6), ("HT20 MCS 7", 65.0, 20, -74.2)]),
    ("LoRa, 868 МГц, 125 кГц", 868.0, AQUA, "^", [
        ("SF12", 0.000293, 14, -137.0), ("SF11", 0.000537, 14, -134.5), ("SF10", 0.000976, 14, -132.0),
        ("SF9", 0.001757, 14, -129.0), ("SF8", 0.003125, 14, -126.0), ("SF7", 0.005468, 14, -123.0)]),
]
VIDEO_MBPS = 1.063          # полезная скорость видеопотока стенда (08.10, 5 м)


def range_m(L, f_mhz, h1=None, h2=None):
    """Расстояние, на котором потери трассы равны L: свободное пространство или
    двухлучевая модель в двухсегментном приближении (если заданы высоты антенн)."""
    d_fs = 1000 * 10 ** ((L - 20 * math.log10(f_mhz) - 32.44) / 20)
    if h1 is None:
        return d_fs
    b = 4 * h1 * h2 / (299.792458 / f_mhz)
    lb = fspl_db(b, f_mhz)
    return d_fs if lb >= L else b * 10 ** ((L - lb) / 40)


def rate_vs_range(path="fig_rate_range.png"):
    fig, ax = plt.subplots(figsize=(6.5, 4.3))
    for name, f, col, mk, modes in TECH:
        xs = [range_m(pt - sens - MARGIN_DB, f) / 1000 for _, _, pt, sens in modes]
        ys = [r for _, r, _, _ in modes]
        ax.plot(xs, ys, color=col, lw=2, marker=mk, ms=7, mec="white", mew=1.2, label=name, zorder=3)
    # опубликованные данные производителя модуля (+20 дБм, полоса не указана) [txbridge, txspec]
    pub_x, pub_y = [0.3, 0.6, 1.2], [15.0, 5.1, 5.3]
    ax.errorbar(pub_x, pub_y, yerr=[[0, 0, 1.3], [0, 0, 1.3]], fmt="o", ms=7, mfc="white", mec=BLUE,
                mew=1.5, ecolor=BLUE, elinewidth=1, capsize=3, zorder=4,
                label="Wi-Fi HaLow: данные производителя\n(+20 дБм, полоса не указана)")
    ax.axhline(VIDEO_MBPS, color=INK2, lw=1, ls="--", zorder=1)
    ax.text(0.031, VIDEO_MBPS * 1.12, "видеопоток стенда 1063 кбит/с", fontsize=9, color=INK2)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(0.03, 600)
    ax.set_ylim(1e-4, 200)
    ax.set_xlabel("Дальность связи, км (свободное пространство, запас 10 дБ)")
    ax.set_ylabel("Скорость физического уровня, Мбит/с")
    ax.grid(True, which="major", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=8.5, frameon=False, loc="upper right", handlelength=2.6)
    ax.text(0.031, 1.4e-4, "* чувствительность для канала 2 МГц — оценка", fontsize=8, color=INK2)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


DISTS_KM = [0.1, 0.3, 0.5, 1, 2, 3, 5, 10, 20]
SCENARIOS = [("Свободное пространство", None, None),
             ("Антенны у земли, 1,5 / 1,5 м", 1.5, 1.5),
             ("Антенна на борту, 1,5 / 50 м", 1.5, 50.0)]


def best_rate(modes, f, d_km, h1, h2):
    ok = [r for _, r, pt, sens in modes if range_m(pt - sens - MARGIN_DB, f, h1, h2) / 1000 >= d_km]
    return max(ok) if ok else None


def fmt_rate(r):
    if r is None:
        return "—"
    if r >= 1:
        return f"{r:g}".replace(".", ",") + " М"
    return f"{r * 1000:.3g}".replace(".", ",") + " к"


def rate_heatmap(path="fig_rate_heatmap.png"):
    from matplotlib.colors import LinearSegmentedColormap, LogNorm
    cmap = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
    norm = LogNorm(vmin=1e-4, vmax=100)
    fig, axes = plt.subplots(3, 1, figsize=(6.5, 5.6), sharex=True)
    for ax, (title, h1, h2) in zip(axes, SCENARIOS):
        for i, (name, f, col, mk, modes) in enumerate(TECH):
            for j, d in enumerate(DISTS_KM):
                r = best_rate(modes, f, d, h1, h2)
                fc = "#f0efec" if r is None else cmap(norm(r))
                ax.add_patch(plt.Rectangle((j, i), 1, 1, fc=fc, ec="white", lw=2))
                dark = r is not None and norm(r) > 0.55
                ax.text(j + 0.5, i + 0.5, fmt_rate(r), ha="center", va="center", fontsize=8.5,
                        color="white" if dark else INK, weight="bold" if r and r >= VIDEO_MBPS else None)
        ax.set_xlim(0, len(DISTS_KM))
        ax.set_ylim(len(TECH), 0)
        ax.set_yticks([i + 0.5 for i in range(len(TECH))])
        ax.set_yticklabels(["Wi-Fi HaLow", "Wi-Fi 2,4 ГГц", "LoRa"], fontsize=9.5)
        ax.set_title(title, fontsize=10, loc="left", color=INK)
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
    axes[-1].set_xticks([j + 0.5 for j in range(len(DISTS_KM))])
    axes[-1].set_xticklabels([f"{d:g}".replace(".", ",") for d in DISTS_KM])
    axes[-1].set_xlabel("Расстояние, км")
    fig.text(0.01, -0.01, "В ячейке — наибольшая скорость физического уровня, бит/с (к — кбит/с, М — Мбит/с), "
             "при которой связь сохраняется с запасом 10 дБ;\nжирным — скорость не ниже видеопотока "
             "стенда (1063 кбит/с); «—» — связи нет. Расчёт автора по паспортным данным.",
             fontsize=8, color=INK2, va="top")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def wall_loss(path="fig_wall.png"):
    """Потери в бетонной стене по 3GPP TR 38.901 (7.4.3.1): L = 5 + 4·f, дБ (f в ГГц)."""
    bands = [("Wi-Fi HaLow\n0,867 ГГц", 0.867, BLUE), ("Wi-Fi\n2,44 ГГц", 2.44, ORANGE),
             ("Wi-Fi\n5,5 ГГц", 5.5, "#eda100")]
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    for i, (lab, f, col) in enumerate(bands):
        v = 5 + 4 * f
        ax.bar(i, v, width=0.55, color=col)
        ax.text(i, v + 0.6, f"{v:.1f}".replace(".", ",") + " дБ", ha="center", fontsize=10, color=INK)
    ax.set_xticks(range(len(bands)))
    ax.set_xticklabels([b[0] for b in bands], fontsize=9.5)
    ax.set_ylabel("Потери в бетонной стене, дБ")
    ax.set_ylim(0, 32)
    ax.grid(True, axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", length=0)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    stand_scheme()
    path_loss()
    throughput_steps()
    print("рисунки готовы")
    rate_vs_range()
    rate_heatmap()
    wall_loss()
