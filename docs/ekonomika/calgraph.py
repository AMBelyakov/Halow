# -*- coding: utf-8 -*-
"""Календарный план НИР в осях «календарные даты — трудоёмкость» (методичка, п. 3.2)."""
from datetime import timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from calc_economics import R

plt.rcParams.update({"font.family": "Times New Roman", "font.size": 11})
stages = R["stages"]
fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=250)

cum = 0
xs, ys = [mdates.date2num(stages[0]["begin"])], [0]
for i, s in enumerate(stages, 1):
    x0 = mdates.date2num(s["begin"])
    x1 = mdates.date2num(s["end"] + timedelta(days=1))
    y0, cum = cum, cum + s["T"]
    xs.append(x1)
    ys.append(cum)
    ax.plot([x0, x1], [y0, cum], color="black", linewidth=1.6)
    ax.plot([x1, x1], [0, cum], color="#999999", linewidth=0.6, linestyle="--")
    ax.plot([x0, x1], [cum, cum], color="#999999", linewidth=0.6, linestyle=":")
    ax.plot(x1, cum, "o", color="black", markersize=4)
    ax.text((x0 + x1) / 2 - 1.5, (y0 + cum) / 2 + 12, str(i), ha="right", va="bottom", fontsize=11,
            fontweight="bold")
    dl = mdates.date2num(s["deadline"]) + 1
    ax.plot(dl, cum, marker="v", color="black", markersize=6, linestyle="none")
    ax.text(x1 + 1, cum - 8, f"{cum}", ha="left", va="top", fontsize=9)

ax.set_xlim(mdates.date2num(stages[0]["begin"] - timedelta(days=3)),
            mdates.date2num(stages[-1]["deadline"] + timedelta(days=6)))
ax.set_ylim(0, R["T_total"] * 1.08)
ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=1))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
plt.setp(ax.get_xticklabels(), rotation=90, fontsize=9)
ax.set_xlabel("Календарные даты, 2026 г.")
ax.set_ylabel("Трудоёмкость нарастающим итогом, чел.-ч")
ax.grid(axis="y", color="#e0e0e0", linewidth=0.6)
ax.plot([], [], "o", color="black", markersize=4, label="окончание стадии")
ax.plot([], [], "v", color="black", markersize=6, label="срок стадии по заданию")
ax.legend(loc="upper left", fontsize=9.5)
fig.tight_layout()
fig.savefig("calgraph.png")
print("saved calgraph.png")
