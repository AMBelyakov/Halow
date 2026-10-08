# -*- coding: utf-8 -*-
"""Календарный график НИР по работам (диаграмма Ганта) по данным calc_economics.R."""
from datetime import timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from calc_economics import R

plt.rcParams.update({"font.family": "Times New Roman", "font.size": 11})

stages, works = R["stages"], R["net"]["works"]
N = len(works)
fig, ax = plt.subplots(figsize=(7.6, 8.2), dpi=250)
money = lambda x: f"{x:,.0f}".replace(",", " ")

for k, w in enumerate(works):
    y = N - 1 - k
    start = mdates.date2num(w["begin"])
    width = (w["end"] - w["begin"]).days + 1
    ax.barh(y, width, left=start, height=0.6, color="#7f7f7f" if w["crit"] else "white",
            edgecolor="black", linewidth=0.8, hatch=None if w["crit"] else "////")
    ax.text(start + width + 0.6, y, ", ".join(w["days"]), ha="left", va="center", fontsize=9.5,
            style="italic")

# границы стадий и контрольные сроки задания
last_k = {}
for k, w in enumerate(works):
    last_k[w["stage"]] = k
for st, k in last_k.items():
    y = N - 1 - k
    if st < len(stages):
        ax.axhline(y - 0.5, color="#555555", linewidth=0.6, linestyle="--")
    dl = mdates.date2num(stages[st - 1]["deadline"]) + 1
    ax.plot(dl, y + 0.45, marker="v", color="black", markersize=7, zorder=3)

labels = [f"{w['i']}–{w['j']}  {w['short']}" for w in works]
ax.set_yticks(range(N))
ax.set_yticklabels(labels[::-1], fontsize=10)
ax.set_ylim(-0.7, N - 0.3)

# заработная плата по работам — столбец справа
first, last = stages[0]["begin"], stages[-1]["deadline"]
x0, x1 = mdates.date2num(first - timedelta(days=2)), mdates.date2num(last + timedelta(days=4))
ax.set_xlim(x0, x1)
tr = ax.get_yaxis_transform()
ax.text(1.015, N - 0.35, "З/п, руб.", transform=tr, ha="left", va="bottom", fontsize=10, fontweight="bold")
for k, w in enumerate(works):
    ax.text(1.015, N - 1 - k, money(w["zp"]), transform=tr, ha="left", va="center", fontsize=10)
ax.text(1.015, -0.62, "Σ " + money(R["zp_tarif"]), transform=tr, ha="left", va="center", fontsize=10,
        fontweight="bold")

ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=1))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
plt.setp(ax.get_xticklabels(), rotation=90, fontsize=9.5)
ax.grid(axis="x", color="#dddddd", linewidth=0.6)
ax.set_axisbelow(True)
ax.set_xlabel("Календарные даты, 2026 г.")

handles = [Patch(facecolor="#7f7f7f", edgecolor="black", label="работа критического пути"),
           Patch(facecolor="white", edgecolor="black", hatch="////", label="работа с резервом времени"),
           plt.Line2D([], [], marker="v", color="black", linestyle="none", label="контрольный срок стадии по заданию")]
ax.legend(handles=handles, loc="upper right", fontsize=9, frameon=True)

fig.tight_layout()
fig.subplots_adjust(right=0.87)
fig.savefig("gantt.png")
print("saved gantt.png")
