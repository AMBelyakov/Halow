# -*- coding: utf-8 -*-
"""Сетевой график НИР («события — работы») по данным calc_economics.R["net"].

Запуск: python3 network.py -> network.png (рисунок главы 4).
"""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch

from calc_economics import R

plt.rcParams.update({"font.family": "serif",
                     "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"],
                     "font.size": 9})
NET = R["net"]
RAD = 0.42
RED = "#c00000"

# координаты событий: три ряда «змейкой», параллельные ветви первой и второй стадий — выше ряда
POS = {1: (0, 2), 2: (1.3, 3.2), 3: (2.6, 2), 4: (3.9, 2), 5: (6.2, 3.2), 6: (7.6, 2), 7: (10, 2),
       8: (10, 0.3), 9: (5, 0.3), 10: (0, 0.3),
       11: (0, -1.4), 12: (5, -1.4), 13: (10, -1.4)}

fig, ax = plt.subplots(figsize=(6.6, 4.0), dpi=250)
ax.set_aspect("equal")
ax.axis("off")


def event(x, y, num, e, l, fs=8.5, crit=True):
    ax.add_patch(Circle((x, y), RAD, fill=True, facecolor="white", edgecolor=RED if crit else "black",
                        linewidth=1.3 if crit else 0.9, zorder=3))
    d = RAD / math.sqrt(2)
    for sx in (-1, 1):
        ax.plot([x - d, x + d], [y - sx * d, y + sx * d], color="black", linewidth=0.5, zorder=4)
    k = 0.58 * RAD
    ax.text(x, y + k, num, ha="center", va="center", fontsize=fs, fontweight="bold", zorder=5)
    ax.text(x - k, y, e, ha="center", va="center", fontsize=fs - 0.5, zorder=5)
    ax.text(x + k, y, l, ha="center", va="center", fontsize=fs - 0.5, zorder=5)
    ax.text(x, y - k, str(l - e) if isinstance(l, int) else "R", ha="center", va="center",
            fontsize=fs - 0.5, zorder=5)


fmt = lambda v: str(int(v)) if float(v).is_integer() else f"{v:g}".replace(".", ",")
for w in NET["works"]:
    (x1, y1), (x2, y2) = POS[w["i"]], POS[w["j"]]
    L = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    a = FancyArrowPatch((x1 + ux * RAD, y1 + uy * RAD), (x2 - ux * RAD, y2 - uy * RAD),
                        arrowstyle="-|>", mutation_scale=8, zorder=2,
                        color=RED if w["crit"] else "black", linewidth=1.6 if w["crit"] else 0.8)
    ax.add_patch(a)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    if abs(uy) < 0.9:                      # горизонтальные и наклонные: t сверху, исполнители снизу
        nx, ny = -uy, ux
        if ny < 0:
            nx, ny = -nx, -ny
        tx, ty, ex_, ey, ha = mx + nx * 0.2, my + ny * 0.2, mx - nx * 0.2, my - ny * 0.2, "center"
    else:                                  # вертикальные: обе подписи с внутренней стороны
        side = -1 if x1 > 5 else 1
        ha = "right" if side < 0 else "left"
        tx, ty, ex_, ey = mx + side * 0.1, my + 0.14, mx + side * 0.1, my - 0.14
    ax.text(tx, ty, fmt(w["t"]), ha=ha, va="center", fontsize=8.5,
            fontweight="bold", color=RED if w["crit"] else "black")
    ax.text(ex_, ey, w["who"], ha=ha, va="center", fontsize=7, style="italic")

for e, (x, y) in POS.items():
    event(x, y, str(e), NET["early"][e], NET["late"][e], crit=e in NET["crit_events"])

# условные обозначения
lx, ly = 0.2, -2.75
ax.add_patch(Circle((lx, ly), RAD, facecolor="white", edgecolor="black", linewidth=0.9, zorder=3))
d = RAD / math.sqrt(2)
for sx in (-1, 1):
    ax.plot([lx - d, lx + d], [ly - sx * d, ly + sx * d], color="black", linewidth=0.5, zorder=4)
k = 0.58 * RAD
for dx, dy, s in ((0, k, "i"), (-k, 0, "tр"), (k, 0, "tп"), (0, -k, "R")):
    ax.text(lx + dx, ly + dy, s, ha="center", va="center", fontsize=7.5, zorder=5,
            style="italic" if s != "i" else "normal")
for n_, s in enumerate(["i — номер события", "tр — ранний срок события, кал. дн.",
                        "tп — поздний срок события, кал. дн.", "R — резерв времени события, кал. дн."]):
    ax.text(lx + 0.6, ly + 0.36 - n_ * 0.25, s, ha="left", va="center", fontsize=7.5)
for n_, (c, lw, s) in enumerate(((RED, 1.6, "работа критического пути"), ("black", 0.8, "некритическая работа"))):
    yy = ly + 0.24 - n_ * 0.34
    ax.add_patch(FancyArrowPatch((5.5, yy), (6.2, yy), arrowstyle="-|>", mutation_scale=8, color=c, linewidth=lw))
    ax.text(6.3, yy, s, ha="left", va="center", fontsize=7.5)

ax.set_xlim(-0.55, 10.55)
ax.set_ylim(-3.25, 3.75)
fig.subplots_adjust(0, 0, 1, 1)
fig.savefig("network.png")
print("saved network.png")
