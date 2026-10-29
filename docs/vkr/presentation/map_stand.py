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
29.10 (пользователь: «рис. 9 упрости, AI detected»): простой план линиями, как на чертеже, — без деревьев,
соседнего дома, стоянки, улицы, поворота и заливок.
Запуск: python map_stand.py -> map_stand.png рядом со скриптом.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
INK = "#000000"
plt.rcParams["font.family"] = "Times New Roman"

fig = plt.figure(figsize=(6.2, 6.0), dpi=200)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(-36, 52)
ax.set_ylim(-48, 37)
ax.set_aspect("equal")
ax.axis("off")

ax.add_patch(Rectangle((8, -46), 12, 80, fc="white", ec=INK, lw=1.6))   # дом с камерой
ax.plot([14, 14], [-46, 34], color=INK, lw=1.0)                          # продольная стена
for k, y in enumerate((28, 8, -12, -32)):                                 # подъезды 1–4 со стороны двора
    ax.add_patch(Rectangle((5.6, y - 1.6), 2.4, 3.2, fc="white", ec=INK, lw=1.2))
    ax.text(3.8, y, str(k + 1), color=INK, fontsize=15, ha="right", va="center")
ax.text(4.5, 33, "подъезды", color=INK, fontsize=14, ha="right", va="center")

cam, me = (9.6, 18), (24.0, 18)                                           # ≈ 11 м по плану, две стены
ax.plot([cam[0], me[0]], [cam[1], me[1]], color=INK, lw=1.4, ls=(0, (5, 3)))
ax.plot(*cam, "o", ms=9, mfc="white", mec=INK, mew=1.8)
ax.plot(*me, "s", ms=9, mfc="white", mec=INK, mew=1.8)
ax.annotate("камера (AP),\n3-й этаж", xy=cam, xytext=(-2, 24), fontsize=16, ha="right", va="center",
            color=INK, arrowprops=dict(arrowstyle="-", color=INK, lw=0.9))
ax.annotate("ноутбук + STA,\nу земли", xy=me, xytext=(27, 27), fontsize=16, ha="left", va="center",
            color=INK, arrowprops=dict(arrowstyle="-", color=INK, lw=0.9))
ax.text(27, 9, "≈ 13 м,\nдве стены,\n≈ 68 дБ", fontsize=16, ha="left", va="center", color=INK)

ax.plot([30, 50], [-42, -42], color=INK, lw=1.6, solid_capstyle="butt")      # масштаб
for x in (30, 50):
    ax.plot([x, x], [-43, -41], color=INK, lw=1.6)
ax.text(40, -40.5, "20 м", color=INK, fontsize=15, ha="center", va="bottom")

fig.savefig(os.path.join(HERE, "map_stand.png"), facecolor="white")
print("ok")
