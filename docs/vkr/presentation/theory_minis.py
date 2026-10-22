# -*- coding: utf-8 -*-
"""Три маленьких графика для слайда 5 (22.10: «много цифр и текста — разбавить картинками»).

Те же модели, что в ВКР: свободное пространство (Фриис), Вайсбергер для леса, двухлучевая
в двухсегментном приближении. Запуск: python theory_minis.py -> theory_fs.png, theory_fol.png,
theory_2ray.png рядом со скриптом.
"""
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BLUE, ORANGE, GREY, INK, GRID = "#2A78D6", "#D2551F", "#8A8F98", "#14213D", "#E3E1DA"
plt.rcParams.update({"font.family": "Arial", "font.size": 19, "axes.edgecolor": GREY,
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})
F_H, F_W = 867.0, 2437.0


def fspl(d_m, f):
    return 32.44 + 20 * math.log10(f) + 20 * math.log10(d_m / 1000)


def wei(d, g):
    return 1.33 * g ** 0.284 * d ** 0.588


def two_ray(d, h1, h2, f=F_H):
    b = 4 * h1 * h2 / (299.792458 / f)
    return fspl(d, f) if d <= b else fspl(b, f) + 40 * math.log10(d / b)


def _ax():
    fig, ax = plt.subplots(figsize=(5.0, 4.0), dpi=150)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    return fig, ax


def plain_log(ax, ticks, fmt):
    ax.set_xticks(ticks)
    ax.set_xticklabels([fmt(t) for t in ticks])
    ax.minorticks_off()


def save(fig, name):
    fig.savefig(os.path.join(HERE, name), bbox_inches="tight", facecolor="white")
    plt.close(fig)


# 1. свободное пространство: две частоты
fig, ax = _ax()
ds = [100 * 10 ** (i / 50) for i in range(0, 101)]          # 0,1–10 км
ax.plot([d / 1000 for d in ds], [fspl(d, F_W) for d in ds], color=ORANGE, lw=2.5)
ax.plot([d / 1000 for d in ds], [fspl(d, F_H) for d in ds], color=BLUE, lw=2.5)
ax.set_xscale("log")
ax.set_xlabel("Расстояние, км")
ax.set_ylabel("Потери, дБ")
ax.text(0.12, fspl(120, F_W) + 13, "2,4 ГГц", color=ORANGE, fontsize=19, weight="bold")
ax.text(2.6, fspl(2600, F_H) - 9, "868 МГц", color=BLUE, fontsize=19, weight="bold")
plain_log(ax, [0.1, 0.3, 1, 3, 10], lambda t: f"{t:g}".replace(".", ","))
ax.annotate("", xy=(1, fspl(1000, F_H)), xytext=(1, fspl(1000, F_W)),
            arrowprops=dict(arrowstyle="<->", color=INK, lw=1.5))
ax.text(1.0, 86, "9 дБ", ha="center", va="top", fontsize=18, weight="bold", color=INK)
save(fig, "theory_fs.png")

# 2. лес: длина участка
fig, ax = _ax()
ls = list(range(14, 401, 2))
ax.plot(ls, [wei(d, 2.44) for d in ls], color=ORANGE, lw=2.5)
ax.plot(ls, [wei(d, 0.867) for d in ls], color=BLUE, lw=2.5)
ax.set_xlabel("Длина участка леса, м")
ax.set_ylabel("Потери в лесу, дБ")
ax.text(200, wei(250, 2.44) + 8, "2,4 ГГц", color=ORANGE, fontsize=19, weight="bold")
ax.text(250, wei(250, 0.867) - 9, "868 МГц", color=BLUE, fontsize=19, weight="bold")
ax.annotate("", xy=(100, wei(100, 0.867)), xytext=(100, wei(100, 2.44)),
            arrowprops=dict(arrowstyle="<->", color=INK, lw=1.5))
ax.text(112, (wei(100, 0.867) + wei(100, 2.44)) / 2 - 7, f"{wei(100, 2.44) - wei(100, 0.867):.1f} дБ на 100 м".replace(".", ","),
        ha="left", va="top", fontsize=19, weight="bold", color=INK)
save(fig, "theory_fol.png")

# 3. двухлучевая: антенны у земли и на борту
fig, ax = _ax()
ds = [10 * 10 ** (i / 50) for i in range(0, 136)]           # 10 м – 5 км
ax.plot(ds, [fspl(d, F_H) for d in ds], color=GREY, lw=1.6, ls="--")
ax.plot(ds, [two_ray(d, 1.5, 1.5) for d in ds], color=ORANGE, lw=2.5)
ax.plot(ds, [two_ray(d, 1.5, 50) for d in ds], color=BLUE, lw=2.5)
b_g, b_50 = 4 * 1.5 * 1.5 / (299.792458 / F_H), 4 * 1.5 * 50 / (299.792458 / F_H)
for b, c in ((b_g, ORANGE), (b_50, BLUE)):
    ax.axvline(b, color=c, lw=1, ls=":")
ax.set_xscale("log")
ax.set_xlabel("Расстояние, м")
ax.set_ylabel("Потери, дБ")
ax.text(b_g * 1.15, 128, f"{b_g:.0f} м", color=ORANGE, fontsize=19, weight="bold")
ax.text(b_50 * 1.12, 63, f"{b_50:.0f} м", color=BLUE, fontsize=19, weight="bold")
ax.text(70, 52, "антенны у земли, 1,5 м", color=ORANGE, fontsize=16)
ax.text(70, 43, "антенна на борту, 50 м", color=BLUE, fontsize=16)
ax.text(1250, 74, "свободное\nпространство", color=GREY, fontsize=15)
plain_log(ax, [10, 30, 100, 300, 1000, 3000], lambda t: f"{t:g}")
ax.set_ylim(40, 135)
save(fig, "theory_2ray.png")
print("ok")
