# -*- coding: utf-8 -*-
"""План трассы «5 м через стену» для слайда 11 в стиле карты (27.10, пользователь: «нарисуй как на картах
рисуют»; 27.10, позже: «живу между 1 и 2 подъездом»). Двор из двух пятиэтажек и дорога — по спутниковому снимку пользователя, подъезды 1–4 — его
нумерация; камера (AP) — в квартире между подъездами 1 и 2 у окна во двор, ноутбук + STA — за своим домом,
с обратной стороны, вне кадра камеры (27.10, пользователь: «чтобы не было вопросов, где я на картинке»; у угла
соседнего дома он попал бы в кадр). Потери на трассе стенда — 67 дБ (приёмник 14 дБм, у камеры −53 дБм); путь
≈ 11 м через две бетонные стены 0,5 м — 52,3 дБ свободного пространства + 2 × 8,5 дБ (3GPP TR 38.901) ≈ 69 дБ.
За соседним домом было бы ≈ 85 дБ — при этом, по опыту 16.10, видео почти стоит, и показатели слайда не годятся.
28.10 (пользователь: «сценарий 2 стены и 3 этажа, он больше похож на полёт БПЛА»; соседняя комната — «бесполезный
сценарий с красивыми числами»): камера (AP) на 3-м этаже, ноутбук + STA у земли за домом; перекрытий на пути нет,
только две стены, обе из гипсокартона (пользователь, 28.10; в опыте 16.10 на пути был бетон, поэтому его 81 дБ
сюда не переносится). Наклонный путь ≈ 13 м (≈ 11 м по плану, ≈ 6 м по высоте). L = FSPL 53,5 + C ≈ 12 (потери плат,
антенн и помещения по трём замерам: стенд 67, 16.10 т.1 66 и т.2 81 дБ, бетон 8,5 дБ по 3GPP TR 38.901)
+ 2 × ≈ 1 дБ гипсокартона (ITU-R P.2040) ≈ 68 дБ — как на стенде.
Запуск: python map_stand.py -> map_stand.png рядом со скриптом.
"""
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Polygon  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GROUND, GREEN, TREE, ROAD, ROAD_EDGE = "#F2EFE9", "#D3E8C6", "#B5D69F", "#FFFFFF", "#D9D3C7"
HOUSE, HOUSE_EDGE, INK, GREY = "#DDD8CF", "#B7AE9F", "#14213D", "#6B7280"
BLUE, ORANGE = "#2A78D6", "#D2551F"
ROT = math.radians(-18)                      # двор повёрнут, как на снимке


def r(x, y):
    return (x * math.cos(ROT) - y * math.sin(ROT), x * math.sin(ROT) + y * math.cos(ROT))


def poly(ax, pts, fc, ec="none", lw=0, z=1):
    ax.add_patch(Polygon([r(*p) for p in pts], closed=True, fc=fc, ec=ec, lw=lw, zorder=z))


def rect(ax, x0, y0, x1, y1, **kw):
    poly(ax, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **kw)


fig = plt.figure(figsize=(6.2, 6.0), dpi=200)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(-52, 57)
ax.set_ylim(-38, 67.5)   # 27.10: улица видна сверху слева, как на снимке пользователя
ax.set_aspect("equal")
ax.axis("off")
fig.patch.set_facecolor(GROUND)

rect(ax, -80, -80, 80, 60, fc=GROUND, z=0)
rect(ax, -44, -60, 34, 41, fc=GREEN, z=1)                   # двор
rect(ax, -90, 44, 90, 52, fc=ROAD, ec=ROAD_EDGE, lw=1.5, z=2)  # дорога
rect(ax, -90, 41, 90, 42.5, fc=ROAD, ec=ROAD_EDGE, lw=1, z=2)    # тротуар
for x, y, s in ((-20, 38, 3.2), (-14, 30, 2.6), (-22, 18, 3.0), (-6, -40, 3.0), (-16, -30, 2.6),
                (2, 34, 2.4), (-4, 12, 2.2), (-24, -10, 2.8), (26, 38, 2.6), (28, -50, 2.8), (-8, -52, 2.4)):
    ax.add_patch(Circle(r(x, y), s, fc=TREE, ec="none", zorder=2))
rect(ax, -24, -46, -14, -26, fc="#E6E3DC", ec=ROAD_EDGE, lw=1, z=2)  # стоянка во дворе

rect(ax, -42, -50, -30, 34, fc=HOUSE, ec=HOUSE_EDGE, lw=1.6, z=3)   # соседний дом
rect(ax, 8, -46, 20, 38, fc=HOUSE, ec=HOUSE_EDGE, lw=1.6, z=3)      # дом с камерой
rect(ax, 13.85, -46, 14.15, 38, fc=HOUSE_EDGE, z=4)                 # 28.10: продольная стена — гипсокартон (пользователь)

for k, y in enumerate((28, 8, -12, -32)):                           # подъезды 1–4 с запада, сверху вниз
    cx, cy = r(5.2, y)
    ax.add_patch(Circle((cx, cy), 2.9, fc="#5F6673", ec="white", lw=1.2, zorder=6))
    ax.text(cx, cy, str(k + 1), color="white", fontsize=13, weight="bold", ha="center", va="center", zorder=7)

cam, me = r(9.6, 18), r(21.0, 18)                                   # квартира -> за домом: ≈ 11 м, две стены
ax.plot([cam[0], me[0]], [cam[1], me[1]], color=INK, lw=2, ls=(0, (4, 3)), zorder=8)
for (x, y), c in ((cam, BLUE), (me, ORANGE)):
    ax.add_patch(Circle((x, y), 2.0, fc=c, ec="white", lw=1.5, zorder=9))
ax.text(*r(-4, 22), "камера (AP),\n3-й этаж", color=BLUE, fontsize=15.5, weight="bold",   # 27.10: без «в квартире» и «я»
        ha="right", va="center", zorder=10, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.95))
ax.plot([cam[0], r(-3.5, 22)[0]], [cam[1], r(-3.5, 22)[1]], color=BLUE, lw=1.2, zorder=8)
mx, my = me
ax.plot([mx, r(27, 26)[0]], [my, r(27, 26)[1]], color=ORANGE, lw=1.2, zorder=8)
ax.text(*r(27.5, 26), "ноутбук\n+ STA\nу земли", color=ORANGE, fontsize=15.5, weight="bold",
        ha="left", va="center", zorder=10, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.95))
lx, ly = r(25, 8)
ax.text(lx, ly, "≈ 13 м,\nдве стены,\n≈ 68 дБ", color=INK, fontsize=15, weight="bold", ha="left", va="center",
        zorder=10, bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.9))
ax.text(*r(-36, -6), "соседний дом", color=GREY, fontsize=15, ha="center", va="center", rotation=72,
        rotation_mode="anchor", zorder=10)
ax.text(*r(-19, -36), "P", color=GREY, fontsize=17, weight="bold", ha="center", va="center", zorder=10)

# масштаб и север
ax.plot([30, 50], [-34, -34], color=INK, lw=2, solid_capstyle="butt", zorder=10)
for x in (30, 50):
    ax.plot([x, x], [-35.2, -32.8], color=INK, lw=2, zorder=10)
ax.text(40, -32, "20 м", color=INK, fontsize=15, ha="center", va="bottom", zorder=10)
ax.annotate("", xy=(49, 57), xytext=(49, 49), arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.6),
            zorder=10)
ax.text(49, 58, "С", color=INK, fontsize=16, weight="bold", ha="center", va="bottom", zorder=10)

fig.savefig(os.path.join(HERE, "map_stand.png"), facecolor=GROUND)
print("ok")
