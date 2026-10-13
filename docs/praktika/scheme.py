# -*- coding: utf-8 -*-
"""Структурная схема системы передачи данных с удалённого объекта (рисунок отчёта о практике).
Запуск: python scheme.py -> scheme.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

plt.rcParams.update({"font.family": "serif",
                     "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"],
                     "font.size": 10})

fig, ax = plt.subplots(figsize=(6.6, 3.0), dpi=250)
ax.set_xlim(0, 13.2)
ax.set_ylim(0, 6)
ax.axis("off")


def box(x, y, w, h, text, lw=1.0, dashed=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="square,pad=0", fill=False, linewidth=lw,
                                linestyle=(0, (4, 3)) if dashed else "-"))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9, linespacing=1.15)


def arrow(x1, y1, x2, y2, text=None, dy=0.22, both=False):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="<|-|>" if both else "-|>",
                                 mutation_scale=9, linewidth=0.9, color="black"))
    if text:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + dy, text, ha="center", va="bottom", fontsize=8)


# бортовой узел
box(0.1, 0.5, 5.0, 5.0, "", lw=1.4, dashed=True)
ax.text(2.6, 5.15, "Бортовой узел (удалённый объект)", ha="center", fontsize=9, style="italic")
box(0.4, 3.4, 1.6, 1.2, "Камера\nOV5640")
box(2.6, 3.4, 2.2, 1.2, "Процессор\nESP32-S3")
box(2.6, 0.9, 2.2, 1.2, "Радиомодуль\nWi-Fi HaLow\nTX-AH-R900P")
box(0.4, 0.9, 1.6, 1.2, "Аккумулятор\n18650")
arrow(2.0, 4.0, 2.6, 4.0, "DVP")
arrow(3.7, 3.4, 3.7, 2.1, both=True)
ax.text(3.8, 2.75, "UART", ha="left", va="center", fontsize=8)
# наземный пункт
box(8.1, 0.5, 5.0, 5.0, "", lw=1.4, dashed=True)
ax.text(10.6, 5.15, "Наземный пункт", ha="center", fontsize=9, style="italic")
box(8.4, 0.9, 2.2, 1.2, "Радиомодуль\nWi-Fi HaLow\nTX-AH-R900P")
box(8.4, 3.4, 2.2, 1.2, "Процессор\nESP32-S3")
box(11.1, 3.4, 1.8, 1.2, "Компьютер:\nприём, запись,\nотображение")
arrow(9.5, 2.1, 9.5, 3.4, both=True)
ax.text(9.6, 2.75, "UART", ha="left", va="center", fontsize=8)
arrow(10.6, 4.0, 11.1, 4.0, "USB")
# радиоканал
arrow(4.8, 1.5, 8.4, 1.5, "радиоканал 866–868 МГц,\nWi-Fi HaLow, ≤ 14 дБм", both=True)
arrow(4.8, 4.25, 8.4, 4.25, "Wi-Fi 2,4 ГГц\n(встроен в ESP32-S3,\nдля сравнения)", both=True)
fig.subplots_adjust(0, 0, 1, 1)
fig.savefig("scheme.png")
print("saved scheme.png")
