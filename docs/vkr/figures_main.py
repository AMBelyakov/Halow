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
    "font.family": "Times New Roman",
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

    # верхний ряд — передающая сторона (объект)
    box(1, 38, 22, 20, "Камера OV5640", "240 × 176,\nRGB565")
    box(35, 38, 30, 20, "ESP32-S3 (STA)", "захват и исправление\nкадра, сжатие JPEG,\nчанки ≤ 1400 Б + CRC")
    box(77, 38, 22, 20, "Модуль\nTX-AH-R900P", "\n\nuart_p2p", accent=True)
    arrow(23.8, 48, 34.2, 48, "DVP")
    arrow(65.8, 48, 76.2, 48, "UART")

    # нижний ряд — приёмная сторона (наземный пункт)
    box(77, 2, 22, 20, "Модуль\nTX-AH-R900P", "\n\nuart_p2p", accent=True)
    box(35, 2, 30, 20, "ESP32-S3 (AP)", "сборка кадров,\nпроверка CRC,\nотчёт 1 раз в секунду")
    box(1, 2, 22, 20, "ПК", "просмотр видео,\nзапись показателей\n(CSV)")
    arrow(76.2, 12, 65.8, 12, "UART")
    arrow(34.2, 12, 23.8, 12, "USB")

    # радиоканал
    ax.add_patch(FancyArrowPatch((86, 37.2), (86, 22.8), arrowstyle="-|>", mutation_scale=12,
                                 lw=1.6, color=BLUE))
    ax.add_patch(FancyArrowPatch((92, 22.8), (92, 37.2), arrowstyle="-|>", mutation_scale=10,
                                 lw=0.9, color=BLUE, linestyle=(0, (3, 2))))
    ax.text(84.2, 30, "видео", ha="right", va="center", fontsize=8.5, color=INK2)
    ax.text(93.8, 30, "отчёт\nприёмника", ha="left", va="center", fontsize=8.5, color=INK2)
    ax.text(50, 30, "Wi-Fi HaLow, 866 МГц", ha="center", va="center", fontsize=10,
            color=BLUE, style="italic")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------ рисунок 2.2
def path_loss(path="fig_pathloss.png"):
    lam = 299.792458 / 866.0                  # длина волны, м
    h1, h2 = 1.5, 50.0                        # наземная антенна и высота объекта, м
    d_bp = 4 * h1 * h2 / lam
    ds = [10 * 10 ** (i / 100) for i in range(0, 271)]   # 10 м … 5 км, логарифмический шаг

    fs868 = [fspl_db(d, 866) for d in ds]
    fs24 = [fspl_db(d, 2437) for d in ds]
    tworay = [fspl_db(d, 866) if d <= d_bp else fspl_db(d_bp, 866) + 40 * math.log10(d / d_bp)
              for d in ds]

    fig, ax = plt.subplots(figsize=(6.5, 3.9))
    ax.set_xscale("log")
    ax.grid(True, which="major", color=GRID, lw=0.6)
    ax.grid(True, which="minor", axis="x", color=GRID, lw=0.3)
    ax.plot(ds, fs24, color=ORANGE, lw=2, ls="--", label="2437 МГц, свободное пространство")
    ax.plot(ds, fs868, color=BLUE, lw=2, label="866 МГц, свободное пространство")
    # до точки излома двухлучевая модель совпадает со свободным пространством,
    # поэтому рисуется только после неё — иначе она закрывает синюю линию
    tail = [(d, v) for d, v in zip(ds, tworay) if d >= d_bp]
    ax.plot([d for d, _ in tail], [v for _, v in tail], color=AQUA, lw=2, ls="-.",
            label="866 МГц, двухлучевая модель (h₁ = 1,5 м, h₂ = 50 м)")
    ax.axvline(d_bp, color=INK2, lw=0.8, ls=":")
    ax.text(d_bp * 1.05, 58, f"точка излома\n{d_bp:.0f} м", fontsize=9, color=INK2, va="bottom")
    # прямые подписи — только там, где линии далеко друг от друга
    ax.text(14, fspl_db(14, 2437) + 2.5, "2437 МГц", fontsize=9, color=INK, rotation=13)
    ax.text(150, fspl_db(150, 866) + 1.8, "866 МГц", fontsize=9, color=INK, rotation=13)
    ax.legend(loc="upper left", frameon=False, fontsize=9, handlelength=2.6)
    ax.set_xlim(10, 5000)
    ax.set_ylim(50, 130)
    ax.set_xlabel("Расстояние, м")
    ax.set_ylabel("Потери на трассе, дБ")
    ax.set_xticks([10, 30, 100, 300, 1000, 3000])
    ax.set_xticklabels(["10", "30", "100", "300", "1000", "3000"])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------ рисунок 3.1
STAGES = [   # (подпись, кбит/с) — из журнала испытаний docs/halow_link_debug.md
    ("01.09  230 400 бод, полоса приёма 8 → 4 МГц", 121),
    ("03.09  384 000 бод, пауза 8 мс", 184),
    ("23.09  384 000 бод, без отладочного фильтра", 222),
    ("24.09  460 800 бод", 235),
    ("24.09  1 Мбод, кольцо модуля 8 КБ", 368),
    ("25.09  3 Мбод, выгребание FIFO в модуле", 523),
    ("25.09  пауза 3 мс, опрос приёма раз в кадр", 708),
]


def throughput_steps(path="fig_throughput.png"):
    labels = [s[0] for s in STAGES][::-1]
    vals = [s[1] for s in STAGES][::-1]
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    bars = ax.barh(range(len(vals)), vals, height=0.62, color=BLUE)
    for b in bars:
        b.set_capstyle("round")
    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels(labels, fontsize=10)
    for i, v in enumerate(vals):
        ax.text(v + 8, i, f"{v}", va="center", fontsize=10, color=INK)
    ax.set_xlim(0, 800)
    ax.set_xlabel("Пропускная способность на приёмнике, кбит/с")
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
