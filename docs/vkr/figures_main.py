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
# Группа 0 — лабораторный этап: стол 0,5–3 м, 240×176, канал 4 МГц на 866 МГц, скорость на приёмнике.
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
    ("08.10  релиз: граница MCS, FEC и досылка (полезная)", 1063, 1),
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
    ax.text(1180, ys[-1] + 0.55, "стол 0,5–3 м, 240×176, 866 МГц, канал 4 МГц", ha="right",
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


if __name__ == "__main__":
    stand_scheme()
    path_loss()
    throughput_steps()
    print("рисунки готовы")
