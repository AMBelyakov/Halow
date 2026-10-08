# -*- coding: utf-8 -*-
"""Рисунки раздела охраны труда: план помещения и компоновка рабочего места (размеры — calc_ot)."""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, FancyArrowPatch, Polygon, Rectangle

import calc_ot as C

plt.rcParams.update({"font.family": "serif", "font.size": 10,
                     # Times New Roman, а где его нет — метрически совместимый Liberation Serif
                     "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"]})
GRAY, DARK = "#d9d9d9", "#555555"


def dim(ax, p1, p2, text, off=(0, 0), rot=0, fs=9):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="<->", mutation_scale=7, linewidth=0.7, color="black"))
    ax.text((p1[0] + p2[0]) / 2 + off[0], (p1[1] + p2[1]) / 2 + off[1], text, ha="center", va="center",
            fontsize=fs, rotation=rot, backgroundcolor="white")


def callout(ax, xy, num, txy):
    ax.plot([xy[0], txy[0]], [xy[1], txy[1]], color="black", linewidth=0.5)
    ax.add_patch(Circle(txy, 0.13, facecolor="white", edgecolor="black", linewidth=0.7, zorder=5))
    ax.text(*txy, str(num), ha="center", va="center", fontsize=8.5, zorder=6)


# ======================================================================= план помещения
A, B, W = C.ROOM_B, C.ROOM_A, 0.12          # ширина 3,0 (по x), длина 4,5 (по y), толщина стены
fig, ax = plt.subplots(figsize=(4.6, 5.6), dpi=250)
ax.set_aspect("equal")
ax.axis("off")
win0, win1 = 1.05, 1.05 + C.WINDOW_W        # окно в нижней стене
door0, door1 = 2.05, 2.8                    # дверь в верхней стене
walls = [(-W, -W, A + 2 * W, W, (win0 + W, win1 + W)),         # низ (с проёмом окна)
         (-W, B, A + 2 * W, W, (door0 + W, door1 + W))]        # верх (с проёмом двери)
for x, y, w, h, (g0, g1) in walls:
    ax.add_patch(Rectangle((x, y), g0 - W, h, facecolor=DARK, edgecolor="none"))
    ax.add_patch(Rectangle((x + g1, y), w - g1, h, facecolor=DARK, edgecolor="none"))
ax.add_patch(Rectangle((-W, -W), W, B + 2 * W, facecolor=DARK, edgecolor="none"))
ax.add_patch(Rectangle((A, -W), W, B + 2 * W, facecolor=DARK, edgecolor="none"))
for yy in (-W, -W / 2, 0):                                     # окно: три линии рамы
    ax.plot([win0, win1], [yy, yy], color="black", linewidth=0.7)
ax.add_patch(Arc((door1, B + W), 2 * (door1 - door0), 2 * (door1 - door0), theta1=90, theta2=180,
                 linewidth=0.6))
ax.plot([door1, door1], [B + W, B + W + (door1 - door0)], color="black", linewidth=1.0)

desk = Rectangle((A - 0.7, 0.05), 0.65, 1.45, facecolor=GRAY, edgecolor="black", linewidth=0.8)
chair = Rectangle((A - 1.2, 0.55), 0.42, 0.42, facecolor="white", edgecolor="black", linewidth=0.8)
bed = Rectangle((0.02, 1.35), 0.95, 2.0, facecolor="white", edgecolor="black", linewidth=0.8)
wardrobe = Rectangle((0.05, B - 0.58), 1.55, 0.55, facecolor="white", edgecolor="black", linewidth=0.8)
radiator = Rectangle((win0 + 0.15, 0.03), C.WINDOW_W - 0.3, 0.1, facecolor=DARK, edgecolor="black", linewidth=0.5)
for p in (desk, chair, bed, wardrobe, radiator):
    ax.add_patch(p)
ax.plot([0.05, 1.6], [B - 0.58, B - 0.03], color="black", linewidth=0.4)
ax.plot([0.05, 1.6], [B - 0.03, B - 0.58], color="black", linewidth=0.4)
ax.add_patch(Rectangle((A - 0.55, 0.45), 0.08, 0.55, facecolor="black"))          # монитор
ax.add_patch(Rectangle((A - 0.42, 1.12), 0.28, 0.2, facecolor="white", edgecolor="black", linewidth=0.6))  # стенд
ax.add_patch(Rectangle((A - 0.1, 3.0), 0.08, 0.3, facecolor="black"))            # огнетушитель
ax.add_patch(Circle((A / 2, B / 2), 0.16, facecolor="white", edgecolor="black", linewidth=0.8))
ax.plot([A / 2 - 0.11, A / 2 + 0.11], [B / 2 - 0.11, B / 2 + 0.11], color="black", linewidth=0.6)
ax.plot([A / 2 - 0.11, A / 2 + 0.11], [B / 2 + 0.11, B / 2 - 0.11], color="black", linewidth=0.6)

callout(ax, (2.4, 1.44), 1, (2.3, 1.9))
callout(ax, (A - 1.0, 0.76), 2, (1.35, 0.95))
callout(ax, (A - 0.28, 1.3), 3, (2.78, 2.0))
callout(ax, (0.5, 2.4), 4, (1.35, 2.9))
callout(ax, (0.8, B - 0.3), 5, (1.9, 3.75))
callout(ax, (win0 + 0.12, -0.06), 6, (0.55, 0.35))
callout(ax, (win0 + 0.75, 0.1), 7, (1.55, 0.45))
callout(ax, ((door0 + door1) / 2, B + 0.05), 8, (2.5, 3.9))
callout(ax, (A - 0.06, 3.15), 9, (2.45, 3.2))
callout(ax, (A / 2 + 0.1, B / 2 + 0.1), 10, (1.9, 2.75))

dim(ax, (-W, -0.5), (A + W, -0.5), f"{C.ROOM_B:.1f} м".replace(".", ","), off=(0, 0))
dim(ax, (win0, -0.3), (win1, -0.3), f"{C.WINDOW_W:.1f} м".replace(".", ","), off=(0, 0), fs=8)
dim(ax, (A + 0.35, 0), (A + 0.35, B), f"{C.ROOM_A:.1f} м".replace(".", ","), off=(0, 0), rot=90)
ax.text(1.1, 1.2, f"S = {C.ROOM_A * C.ROOM_B:.1f} м²".replace(".", ","), fontsize=9.5, style="italic")
ax.set_xlim(-0.35, A + 0.6)
ax.set_ylim(-0.75, B + 0.85)
fig.subplots_adjust(0, 0, 1, 1)
fig.savefig("plan.png")
plt.close(fig)

# ======================================================================= компоновка рабочего места
fig, ax = plt.subplots(figsize=(6.2, 4.4), dpi=250)
ax.set_aspect("equal")
ax.axis("off")
DH = C.DESK_H_MM                  # 725
SEAT = 420
EYE_H = 1170                      # высота глаз сидящего над полом (середина 1130–1220)
ED = C.EYE_SCREEN_MM              # 650
desk_x0, desk_x1 = 0, 800
# стол
ax.add_patch(Rectangle((desk_x0, DH - 25), desk_x1, 25, facecolor=GRAY, edgecolor="black", linewidth=0.8))
ax.add_patch(Rectangle((desk_x0, 0), 30, DH - 25, facecolor=GRAY, edgecolor="black", linewidth=0.8))
ax.plot([desk_x1 - 450, desk_x1 - 450], [0, 600], color=DARK, linewidth=0.6, linestyle="--")
ax.plot([desk_x1 - 450, desk_x1], [600, 600], color=DARK, linewidth=0.6, linestyle="--")
# монитор
eye = (desk_x1 + 330, EYE_H)
ang = math.radians(C.MON_ANGLE)
scr = (eye[0] - ED * math.cos(ang), eye[1] - ED * math.sin(ang))
ax.add_patch(Polygon([(scr[0] - 25, scr[1] - 180), (scr[0] + 5, scr[1] - 180), (scr[0] + 35, scr[1] + 150),
                      (scr[0] + 5, scr[1] + 150)], closed=True, facecolor="black"))
ax.plot([scr[0] - 10, scr[0] - 10], [DH, scr[1] - 180], color="black", linewidth=2)
ax.add_patch(Rectangle((scr[0] - 80, DH), 150, 12, facecolor="black"))
# клавиатура
ax.add_patch(Rectangle((desk_x1 - 330, DH), 250, 25, facecolor="white", edgecolor="black", linewidth=0.7))
# стул
cx = desk_x1 + 320
ax.add_patch(Rectangle((cx - 200, SEAT - 40), 440, 40, facecolor="white", edgecolor="black", linewidth=0.8))
ax.add_patch(Polygon([(cx + 230, SEAT), (cx + 270, SEAT), (cx + 330, SEAT + 520), (cx + 290, SEAT + 520)],
                     closed=True, facecolor="white", edgecolor="black", linewidth=0.8))
ax.plot([cx + 20, cx + 20], [60, SEAT - 40], color="black", linewidth=2)
ax.plot([cx - 160, cx + 200], [60, 60], color="black", linewidth=2)
# человек (упрощённо)
hip = (cx + 150, SEAT + 20)
knee = (desk_x1 - 60, SEAT + 40)
ankle = (desk_x1 - 90, 60)
shoulder = (cx + 180, EYE_H - 180)
elbow = (cx + 150, DH + 90)
hand = (desk_x1 - 180, DH + 45)
for a, b in ((hip, knee), (knee, ankle), (hip, shoulder), (shoulder, elbow), (elbow, hand)):
    ax.plot([a[0], b[0]], [a[1], b[1]], color="#444444", linewidth=5, solid_capstyle="round")
ax.plot([ankle[0], ankle[0] - 120], [30, 30], color="#444444", linewidth=5, solid_capstyle="round")
ax.add_patch(Circle((eye[0] + 55, eye[1] + 20), 95, facecolor="white", edgecolor="#444444", linewidth=2))
ax.plot(*eye, "o", color="black", markersize=2.5)
# линия взгляда и горизонталь
ax.plot([eye[0], scr[0] + 20], [eye[1], scr[1]], color="black", linewidth=0.7, linestyle="-.")
ax.plot([eye[0], scr[0] - 60], [eye[1], eye[1]], color="black", linewidth=0.5, linestyle=":")
ax.text(eye[0] - 175, eye[1] - 62, f"{C.MON_ANGLE}°", fontsize=8.5)
# пол
ax.plot([-100, cx + 450], [0, 0], color="black", linewidth=1.2)
# размеры
dim(ax, (-80, 0), (-80, DH), f"{DH}", rot=90)
dim(ax, (cx + 380, 0), (cx + 380, SEAT), C.SEAT_H_MM.split(" ")[0], rot=90)
dim(ax, (desk_x1 - 450, 250), (desk_x1, 250), "450", fs=8.5)
dim(ax, (desk_x1 - 470, 0), (desk_x1 - 470, 600), "600", rot=90, fs=8.5)
ax.text((scr[0] + eye[0]) / 2 - 110, (scr[1] + eye[1]) / 2 + 5, f"{ED}", ha="center", va="bottom",
        fontsize=9, rotation=math.degrees(ang))
dim(ax, (cx + 520, 0), (cx + 520, EYE_H), "1130–1220", rot=90)
ax.set_xlim(-180, cx + 600)
ax.set_ylim(-60, EYE_H + 180)
fig.subplots_adjust(0, 0, 1, 1)
fig.savefig("layout.png")
print("saved plan.png, layout.png")
