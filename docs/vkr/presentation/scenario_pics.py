# -*- coding: utf-8 -*-
"""Три картинки для слайда 13 «сценарий — трудности — решения» (27.10, пользователь: «построить вокруг
сценарий-трудности-решения, желательно с картинками»). Запуск: python scenario_pics.py ->
sc_range.png, sc_video.png, sc_board.png рядом со скриптом.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BLUE, ORANGE, INK, GREY, GROUND, RED = "#2A78D6", "#D2551F", "#14213D", "#8A8F98", "#B5D69F", "#B23A2E"
plt.rcParams.update({"font.family": "Arial", "font.size": 15})


def canvas():
    fig = plt.figure(figsize=(5.0, 2.8), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 56)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    return fig, ax


def save(fig, name):
    fig.savefig(os.path.join(HERE, name), facecolor="white")
    plt.close(fig)


def box(ax, x, y, w, h, text, fc, ec, tc=INK, fs=14, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=2", fc=fc, ec=ec, lw=1.6))
    ax.text(x + w / 2, y + h / 2, text, color=tc, fontsize=fs, ha="center", va="center",
            weight="bold" if bold else "normal")


# 1. полёт на удалении: прямой и отражённый от земли луч, антенна у земли и на борту
fig, ax = canvas()
ax.add_patch(Rectangle((0, 0), 100, 8, fc=GROUND, ec="none"))
ax.plot([10, 10], [8, 16], color=INK, lw=3)                          # мачта пункта, 1,5 м
ax.add_patch(Polygon([(7, 16), (13, 16), (10, 20)], fc=INK))
ax.text(1, 13, "1,5 м", fontsize=13, color=INK, va="center")
dx, dy = 84, 46                                                      # БПЛА на высоте 50 м
ax.plot([dx - 7, dx + 7], [dy, dy], color=INK, lw=3)
for x in (dx - 7, dx + 7):
    ax.plot([x - 3, x + 3], [dy + 1.5, dy + 1.5], color=INK, lw=2)
ax.add_patch(Rectangle((dx - 3, dy - 3), 6, 3, fc=INK))
ax.plot([10, dx], [20, dy - 3], color=BLUE, lw=2.4)                  # прямой луч
rx = 10 + (dx - 10) * 12 / (12 + 38)                                 # точка отражения
ax.plot([10, rx, dx], [20, 8, dy - 3], color=ORANGE, lw=2, ls=(0, (4, 3)))
ax.annotate("", xy=(dx + 11, 8), xytext=(dx + 11, dy - 2), arrowprops=dict(arrowstyle="<->", color=GREY, lw=1.4))
ax.text(dx + 12.5, 27, "50 м", fontsize=13, color=INK, rotation=90, va="center")
ax.text(30, 40, "прямая волна", fontsize=13, color=BLUE, weight="bold")
ax.text(46, 10.5, "отражённая от земли", fontsize=13, color=ORANGE, weight="bold")
save(fig, "sc_range.png")

# 2. видео с борта: камера -> процессор -> UART (узкое место) -> радиомодуль -> эфир
fig, ax = canvas()
box(ax, 2, 30, 18, 12, "камера", "#F3F1EC", GREY)
box(ax, 26, 30, 20, 12, "ESP32-S3", "#F3F1EC", GREY)
box(ax, 70, 30, 17, 12, "TX-AH", "#E4ECF7", BLUE, BLUE, bold=True)
ax.annotate("", xy=(25, 36), xytext=(21, 36), arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.6))
ax.add_patch(Polygon([(47, 40), (51, 37.2), (65, 37.2), (69, 40), (69, 32), (65, 34.8), (51, 34.8), (47, 32)],
                     fc="#F6D7CF", ec=RED, lw=1.6))                  # сужение — UART
ax.text(58, 46, "UART ≤ 1,8 Мбит/с", fontsize=13.5, color=RED, weight="bold", ha="center")
ax.plot([45, 45, 72, 72], [27, 14, 14, 27], color=BLUE, lw=2, ls=(0, (4, 3)))
ax.text(58, 7, "SPI / SDIO — без сужения", fontsize=13.5, color=BLUE, weight="bold", ha="center")
for k in range(3):                                                    # эфир
    ax.add_patch(matplotlib.patches.Arc((90, 36), 5 + 4 * k, 9 + 6 * k, theta1=-50, theta2=50, color=BLUE, lw=1.6))
save(fig, "sc_video.png")

# 3. своя электроника (27.10, пользователь: «как на БПЛА до и после находятся камера и TX-AH»):
# до — одна плата под корпусом, камера вплотную к радиомодулю; после — камера снизу спереди,
# радиомодуль с антенной сверху на корпусе, между ними кабель (SPI/SDIO)
def drone(ax, x0):
    for xa in (x0 + 4, x0 + 38):                                     # лучи и винты — под корпусом
        ax.plot([x0 + 21, xa], [26, 31], color="#2D3748", lw=2.2, zorder=1)
        ax.plot([xa - 5, xa + 5], [32.5, 32.5], color=GREY, lw=2.4, zorder=1)
        ax.plot([xa, xa], [31, 32.5], color="#2D3748", lw=2, zorder=1)
    ax.add_patch(FancyBboxPatch((x0 + 9, 22), 24, 7, boxstyle="round,pad=0.4,rounding_size=2", fc="#4A5568",
                                ec="#2D3748", lw=1.4, zorder=2))
    for xl, dx in ((x0 + 9.5, -3), (x0 + 32.5, 3)):                  # опоры — наружу
        ax.plot([xl, xl + dx], [22, 13], color="#2D3748", lw=1.8, zorder=1)


def lens(ax, x, y):
    ax.add_patch(Rectangle((x - 3.2, y - 3.2), 6.4, 6.4, fc="#1A1A1A", ec="#555555", lw=1, zorder=3))
    ax.add_patch(matplotlib.patches.Circle((x, y), 2.0, fc="#3A3A3A", ec="#999999", lw=1, zorder=4))


def radio(ax, x, y, ant_up):
    ax.add_patch(Rectangle((x - 4, y - 3), 8, 6, fc="#C9CED6", ec="#555555", lw=1, zorder=3))
    ax.text(x, y, "TX-AH", fontsize=7.5, color=INK, ha="center", va="center", weight="bold", zorder=4)
    if ant_up:
        ax.plot([x + 2.5, x + 2.5], (y + 3, y + 11), color=INK, lw=2)
    else:
        ax.plot([x + 4, x + 9], (y, y - 3), color=INK, lw=2)


fig, ax = canvas()
ax.plot([50, 50], [2, 54], color="#D0CCC2", lw=1.5)
ax.text(25, 49, "до", fontsize=16, color=RED, weight="bold", ha="center")
ax.text(75, 49, "после", fontsize=16, color=BLUE, weight="bold", ha="center")
# до: одна плата под корпусом
drone(ax, 3)
ax.add_patch(Rectangle((13, 13.5), 20, 7, fc="#2F5D50", ec="#1E3D34", lw=1.2, zorder=2))
lens(ax, 17.5, 17)
radio(ax, 28.3, 17, ant_up=False)
for k in range(2):
    ax.add_patch(matplotlib.patches.Arc((21.4, 17), 2 + 2 * k, 4 + 3 * k, theta1=-60, theta2=60, color=RED, lw=1.4, zorder=5))
ax.text(25, 1.5, "одна плата: камера\nвплотную к TX-AH", fontsize=11.5, color=INK, ha="center", va="bottom")
# после: камера снизу спереди, радиомодуль с антенной сверху
drone(ax, 53)
lens(ax, 64, 18)
radio(ax, 78, 32.5, ant_up=True)
ax.plot([64, 64, 78, 78], [21.2, 25, 25, 29.5], color=BLUE, lw=1.6, ls=(0, (3, 2)), zorder=5)
ax.text(69, 17, "SPI / SDIO", fontsize=10.5, color=BLUE, ha="left", va="center", weight="bold")
ax.text(75, 1.5, "камера снизу, TX-AH\nс антенной сверху", fontsize=11.5, color=INK, ha="center", va="bottom")
save(fig, "sc_board.png")
print("ok")
