# -*- coding: utf-8 -*-
"""Сетевой график НИР по данным calc_economics.R["net"] — простой, как в принятом образце:
кружки событий с номерами, над стрелкой — продолжительность работы, кал. дн.;
критический путь выделен, ожидание (без затрат труда) — пунктиром.

13.10: прежний график (13 событий, сектора ранних и поздних сроков) — network.py.bak-2026-10-13.
Запуск: python network.py -> network.png (рисунок главы 4).
"""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch

from calc_economics import DUMMY, R

plt.rcParams.update({"font.family": "serif",
                     "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"],
                     "font.size": 11})
NET = R["net"]
RAD = 0.32
POS = {1: (0, 0), 2: (1.9, 0), 3: (3.4, 1.3), 4: (4.9, 0), 5: (6.8, 0), 6: (8.7, 0), 7: (10.6, 0)}

fig, ax = plt.subplots(figsize=(6.6, 1.9), dpi=250)
ax.set_aspect("equal")
ax.axis("off")


def arrow(i, j, crit, dashed=False):
    (x1, y1), (x2, y2) = POS[i], POS[j]
    L = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    ax.add_patch(FancyArrowPatch((x1 + ux * RAD, y1 + uy * RAD), (x2 - ux * RAD, y2 - uy * RAD),
                                 arrowstyle="-|>", mutation_scale=10, zorder=2, color="black",
                                 linewidth=2.0 if crit else 0.9,
                                 linestyle=(0, (4, 3)) if dashed else "-"))
    return (x1 + x2) / 2, (y1 + y2) / 2, ux, uy


for w in NET["works"]:
    mx, my, ux, uy = arrow(w["i"], w["j"], w["crit"])
    nx, ny = -uy, ux
    ax.text(mx + nx * 0.25, my + ny * 0.25, str(w["t"]), ha="center", va="center",
            fontsize=11, fontweight="bold" if w["crit"] else "normal")
for i, j, t in DUMMY:                    # ожидание (без затрат труда) — пунктир, на критическом пути
    mx, my, ux, uy = arrow(i, j, True, dashed=True)
    ax.text(mx - uy * 0.25, my + ux * 0.25, str(t), ha="center", va="center", fontsize=11,
            fontweight="bold")

for e, (x, y) in POS.items():
    crit = e in NET["crit_events"]
    ax.add_patch(Circle((x, y), RAD, facecolor="white", edgecolor="black",
                        linewidth=2.0 if crit else 0.9, zorder=3))
    ax.text(x, y, str(e), ha="center", va="center", fontsize=11, zorder=4)

ax.set_xlim(-0.45, 11.05)
ax.set_ylim(-0.5, 1.75)
fig.subplots_adjust(0, 0, 1, 1)
fig.savefig("network.png")
print("saved network.png")
