# -*- coding: utf-8 -*-
"""План опыта эквивалентного затухания 16.10.2026 (15-й этаж, блок общежития).

Расстояния — со слов пользователя: камера -> точка 1 5,6 м (за стеной: гипсокартон + бетон);
от точки 1 — 1,5 м вправо, П-образный поворот через открытую входную дверь блока (не учитывается)
в общий коридор и по нему влево: 6 м до точки 2, ещё 1,5 м до точки 3 (видео HaLow стоит, Wi-Fi
рвётся) и ещё 1,5 м до точки 4 (обрыв HaLow). Между рядом точки 1 и коридором — бетонная несущая
стена; шаг между рядами (CORR_DY) принят условно. Протяжённость стен на плане условна.
Потери трассы L — из журналов tools/logs/range_eq_halow_20261016_1702 и range_eq_wifi_20261016_1754.
Запуск: python plan_range_eq.py -> plan_range_eq.png
"""
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

plt.rcParams["font.family"] = "DejaVu Sans"
HERE = os.path.dirname(os.path.abspath(__file__))

CORR_DY = 1.2                       # от ряда точки 1 до оси общего коридора, м (условно)
CAM = (0.0, 0.0)
P1 = (0.0, 5.6)
TURN = (1.5, P1[1])
CORR_Y = P1[1] + CORR_DY
P2 = (TURN[0] - 6.0, CORR_Y)
P3 = (P2[0] - 1.5, CORR_Y)          # видео HaLow 0 кбит/с, Wi-Fi обрыв
P4 = (P3[0] - 1.5, CORR_Y)          # обрыв HaLow
WALL1_Y = 5.0                       # стена у точки 1 (гипсокартон + бетон)
WALL2_Y = P1[1] + CORR_DY / 2       # бетонная несущая стена между рядами
BLUE = "#1f4e79"


def dist(p):
    return math.hypot(p[0] - CAM[0], p[1] - CAM[1])


def m(v):
    return f"{v:.1f}".replace(".", ",")


def fspl(d_m, f_mhz):
    return 20 * math.log10(d_m) + 20 * math.log10(f_mhz) - 27.55


fig, ax = plt.subplots(figsize=(9.0, 7.6), dpi=200)
ax.set_aspect("equal")
ax.axis("off")

# стены
ax.add_patch(Rectangle((-9.0, WALL1_Y - 0.1), 12.0, 0.2, facecolor="#bdbdbd", edgecolor="black", lw=0.7))
ax.text(3.15, WALL1_Y, "стена: гипсокартон 0,75 м\n+ бетон 0,5 м (шагами)", va="center", fontsize=8)
ax.add_patch(Rectangle((-9.0, WALL2_Y - 0.14), 10.0, 0.28, facecolor="#6d6d6d", edgecolor="black", lw=0.7))
ax.add_patch(Rectangle((1.8, WALL2_Y - 0.14), 1.2, 0.28, facecolor="#6d6d6d", edgecolor="black", lw=0.7))
ax.text(3.15, WALL2_Y + 0.05, "бетонная несущая стена", va="center", fontsize=8)
ax.text(1.4, WALL2_Y + 0.55, "дверь блока\n(открыта)", ha="center", va="bottom", fontsize=7, color="#555555")

# маршрут: вверх 5,6 -> вправо 1,5 -> П-поворот через дверь -> влево по коридору
ax.annotate("", xy=P1, xytext=CAM, arrowprops=dict(arrowstyle="->", color=BLUE, lw=1.4))
ax.plot([P1[0], TURN[0], TURN[0], P2[0]], [P1[1], TURN[1], CORR_Y, CORR_Y], color=BLUE, lw=1.4)
ax.annotate("", xy=P4, xytext=P2, arrowprops=dict(arrowstyle="->", color=BLUE, lw=1.4))
ax.text(-0.15, 2.8, "5,6 м", rotation=90, ha="right", va="center", fontsize=8.5, color=BLUE)
ax.text(0.75, P1[1] - 0.12, "1,5 м", ha="center", va="top", fontsize=8, color=BLUE)
ax.text((TURN[0] + P2[0]) / 2, CORR_Y + 0.12, "6 м", ha="center", va="bottom", fontsize=8.5, color=BLUE)
for a, b in ((P2, P3), (P3, P4)):
    ax.text((a[0] + b[0]) / 2, CORR_Y - 0.12, "1,5 м", ha="center", va="top", fontsize=7.5, color=BLUE)

# прямые камера -> точки
for p in (P2, P3, P4):
    ax.plot([CAM[0], p[0]], [CAM[1], p[1]], color="#999999", lw=0.6, ls="-.")

# камера
ax.add_patch(Rectangle((CAM[0] - 0.3, CAM[1] - 0.3), 0.6, 0.6, facecolor="black"))
ax.text(CAM[0] + 0.5, CAM[1], "камера (стол в комнате)\nHaLow 14 дБм / Wi-Fi 20 дБм", va="center", fontsize=8.5)


def point(p, name, lines, color, box_xy):
    ax.plot(*p, "o", color=color, markersize=9, zorder=3)
    ax.text(p[0], p[1] + 0.3, name, ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.annotate("\n".join(lines), xy=p, xytext=box_xy, fontsize=7.6, va="center",
                arrowprops=dict(arrowstyle="-", color=color, lw=0.7),
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor=color, lw=0.9))


point(P1, "1", [f"{m(dist(P1))} м по прямой, 1 стена",
                "HaLow: L = 66 дБ, 923 кбит/с, потери 2 %",
                "Wi-Fi: L = 75 дБ, ~800 кбит/с, потери 3 %"], "#2e7d32", (-8.8, 3.2))
point(P2, "2", [f"{m(dist(P2))} м по прямой, 2 стены",
                "HaLow: L = 81 дБ, видео идёт, потери 9 %",
                "Wi-Fi: L = 96 дБ, видео ~0, потери 66 %"], "#f9a825", (-3.2, 9.6))
point(P3, "3", [f"{m(dist(P3))} м — HaLow: видео стоит (L ≈ 92 дБ)",
                "Wi-Fi: обрыв связи"], "#ef6c00", (-4.0, 11.0))
point(P4, "4", [f"{m(dist(P4))} м — HaLow: обрыв связи"], "#c62828", (-8.8, 9.6))

ax.set_xlim(-9.2, 6.6)
ax.set_ylim(-0.8, 12.2)
ax.text(-9.0, 12.0, "План опыта, 15-й этаж (масштаб по расстояниям; протяжённость стен условна)",
        fontsize=9, fontweight="bold")
fig.subplots_adjust(0.01, 0.01, 0.99, 0.99)
fig.savefig(os.path.join(HERE, "plan_range_eq.png"))

# сводка: превышение измеренных потерь над свободным пространством
print("точка  d,м   FSPL868  L_HaLow  избыт.  FSPL2442  L_WiFi  избыт.")
for name, p, lh, lw in (("1", P1, 66, 75), ("2", P2, 81, 96)):
    d = dist(p)
    a, b = fspl(d, 868), fspl(d, 2442)
    print(f"{name:5} {d:5.1f}  {a:7.1f}  {lh:7}  {lh - a:6.1f}  {b:8.1f}  {lw:6}  {lw - b:6.1f}")
for name, p in (("3", P3), ("4", P4)):
    print(f"{name:5} {dist(p):5.1f}  {fspl(dist(p), 868):7.1f}")
