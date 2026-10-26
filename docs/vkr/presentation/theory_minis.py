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


def proj(ax, x, ys, cols, label, gap, lx=None):
    """22.10: проекции точек кривых на ось потерь — значения стоят делениями на самой оси,
    разница подписана между пунктирами; соседние штатные деления ближе gap убираются."""
    x0, yl = ax.get_xlim()[0], ax.get_ylim()
    for y, c in zip(ys, cols):
        ax.hlines(y, x0, x, colors=c, linestyles="--", lw=1.4)
        ax.plot([x], [y], "o", color=c, ms=6, zorder=5)
    base = [t for t in ax.get_yticks() if yl[0] <= t <= yl[1] and all(abs(t - y) >= gap for y in ys)]
    ticks = sorted(base + list(ys))
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{t:.1f}".replace(".", ",") if t in ys else f"{t:g}" for t in ticks])
    for tl, t in zip(ax.get_yticklabels(), ticks):
        if t in ys:
            tl.set_color(cols[list(ys).index(t)])
            tl.set_fontweight("bold")
            tl.set_fontsize(17)
    if lx is None:
        ax.text(0.03, sum(ys) / 2, label, color=INK, fontsize=16, weight="bold", ha="left", va="center",
                transform=ax.get_yaxis_transform())
    else:
        ax.text(lx, sum(ys) / 2, label, color=INK, fontsize=16, weight="bold", ha="left", va="center")
    ax.set_xlim(left=x0)
    ax.set_ylim(yl)


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
ax.text(1.6, 118, "2,4 ГГц", color=ORANGE, fontsize=19, weight="bold", ha="right")
ax.text(3.2, fspl(3200, F_H) - 11, "868 МГц", color=BLUE, fontsize=19, weight="bold")
plain_log(ax, [0.1, 0.3, 1, 3, 10], lambda t: f"{t:g}".replace(".", ","))
ax.set_xlim(0.09, 11)
proj(ax, 1, (fspl(1000, F_W), fspl(1000, F_H)), (ORANGE, BLUE), "9 дБ", 6)
save(fig, "theory_fs.png")

# 2. лес (27.10, пользователь: «проекцию на 1 км, а не упоминание в тексте»): потери на трассе с участком
# леса 100 м от длины трассы — свободное пространство + добавка Вайсбергера; проекции на ось потерь на 1 км
fig, ax = _ax()
ds = [100 * 10 ** (i / 50) for i in range(0, 101)]          # 0,1–10 км
FW, FH = wei(100, 2.44), wei(100, 0.867)
ax.plot([d / 1000 for d in ds], [fspl(d, F_W) + FW for d in ds], color=ORANGE, lw=2.5)
ax.plot([d / 1000 for d in ds], [fspl(d, F_H) + FH for d in ds], color=BLUE, lw=2.5)
ax.set_xscale("log")
ax.set_xlabel("Расстояние, км")
ax.set_ylabel("Потери, дБ")
ax.text(0.65, 136, "2,4 ГГц", color=ORANGE, fontsize=19, weight="bold", ha="right")
ax.text(3.2, fspl(3200, F_H) + FH - 11, "868 МГц", color=BLUE, fontsize=19, weight="bold")
plain_log(ax, [0.1, 0.3, 1, 3, 10], lambda t: f"{t:g}".replace(".", ","))
ax.set_xlim(0.09, 11)
_w, _h = fspl(1000, F_W) + FW, fspl(1000, F_H) + FH
proj(ax, 1, (_w, _h), (ORANGE, BLUE), f"{_w - _h:.1f} дБ".replace(".", ","), 6)
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
ax.text(b_g * 1.15, 128, f"{b_g:.0f} м", color=ORANGE, fontsize=17, weight="bold")
ax.text(b_50 / 1.12, 128, f"{b_50:.0f} м", color=BLUE, fontsize=17, weight="bold", ha="right")
ax.text(31, 50, "у земли, 1,5 м", color=ORANGE, fontsize=15, weight="bold")
ax.text(31, 43, "на борту, 50 м", color=BLUE, fontsize=15, weight="bold")
ax.text(1150, 70, "свободное\nпространство", color=GREY, fontsize=14)
plain_log(ax, [10, 30, 100, 300, 1000, 3000], lambda t: f"{t:g}")
ax.set_ylim(40, 135)
ax.set_xlim(8, 6000)
_g, _a = two_ray(1000, 1.5, 1.5), two_ray(1000, 1.5, 50)
proj(ax, 1000, (_g, _a), (ORANGE, BLUE), f"{_g - _a:.0f} дБ", 8)
save(fig, "theory_2ray.png")
print("ok")
