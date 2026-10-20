# -*- coding: utf-8 -*-
"""Рисунки раздела охраны труда: план помещения, размещение светильников, рабочее место и зоны
досягаемости. Размеры — calc_ot (план согласован с автором 15.10.2026)."""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, FancyArrowPatch, Polygon, Rectangle, Wedge

import calc_ot as C
from calc_ot import R

plt.rcParams.update({"font.family": "serif", "font.size": 10,
                     # Times New Roman, а где его нет — метрически совместимый Liberation Serif
                     "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"]})
GRAY, WALL = "#d9d9d9", "#444444"
fmt = lambda x, d=1: f"{x:.{d}f}".replace(".", ",")

# ======================================================================= геометрия помещения
# x — вправо от левой стены, yd — вниз от верхней стены (как на эскизе), м
W, B_L, B_R = C.MAIN_B, C.MAIN_A_LEFT, C.MAIN_A_RIGHT
WV, HV, N0, T = C.MAIN_B + C.VEST_B, C.VEST_A, C.STEP_X, 0.15
LT = B_R
Y = lambda yd: LT - yd
INNER = [(0, 0), (WV, 0), (WV, HV), (W, HV), (W, B_R), (N0, B_R), (N0, B_L), (0, B_L)]
OUTER = [(-T, -T), (WV + T, -T), (WV + T, HV + T), (W + T, HV + T), (W + T, B_R + T), (N0 - T, B_R + T),
         (N0 - T, B_L + T), (-T, B_L + T)]
W0, W1 = 1.1, 1.1 + C.WINDOW_W              # окно в левой стене
D0, D1 = 0.55, 1.45                         # дверь в правой стене прихожей
DW, DD, CH = C.DESK_MM[0] / 1000, C.DESK_MM[1] / 1000, 0.55
DESKS = [(0.8, 0, DD, DW), (1.5, 0, DW, DD), (2.9, 0, DW, DD),
         (0, 3.6, DW, DD), (0, 4.3, DW, DD), (0, 7.0, DW, DD), (0, 7.7, DW, DD),
         (W - DW, 2.6, DW, DD), (W - DW, 4.4, DD, DW), (W - DW, 6.8, DD, DW), (W - DW, 8.2, DW, DD)]
CHAIRS = [(0.2, 0.45), (1.93, 0.75), (3.33, 0.75),
          (0.42, 3.0), (0.42, 5.05), (0.42, 6.4), (0.42, 8.45),
          (4.03, 3.35), (4.4, 4.85), (4.4, 7.25), (4.03, 9.0)]
MY = 1                                      # рабочее место автора — средний стол верхнего ряда


def room(ax, furniture=True, light_furn=False):
    ax.add_patch(Polygon([(x, Y(y)) for x, y in OUTER], closed=True, facecolor=WALL, edgecolor="none"))
    ax.add_patch(Polygon([(x, Y(y)) for x, y in INNER], closed=True, facecolor="white", edgecolor="none"))
    lw, ec = (0.5, "#9a9a9a") if light_furn else (0.8, "black")

    def r(x0, yd0, w, h, fc="white", label=None, fs=7.5, z=3, lw_=None):
        ax.add_patch(Rectangle((x0, Y(yd0 + h)), w, h, facecolor=fc, edgecolor=ec,
                               linewidth=lw if lw_ is None else lw_, zorder=z))
        if label:
            ax.text(x0 + w / 2, Y(yd0 + h / 2), label, ha="center", va="center", fontsize=fs,
                    color=ec, zorder=z + 1)
    # окно (три створки) и батарея под ним
    ax.add_patch(Rectangle((-T, Y(W1)), T, W1 - W0, facecolor="white", edgecolor="black", linewidth=0.6, zorder=4))
    ax.plot([-T / 2, -T / 2], [Y(W0), Y(W1)], color="black", linewidth=0.5, zorder=5)
    for k in (1, 2):
        yy = W0 + k * C.WINDOW_W / 3
        ax.plot([-T, 0], [Y(yy), Y(yy)], color="black", linewidth=0.5, zorder=5)
    # дверь
    ax.add_patch(Rectangle((WV, Y(D1)), T, D1 - D0, facecolor="white", edgecolor="none", zorder=4))
    ax.add_patch(Arc((WV, Y(D1)), 2 * (D1 - D0), 2 * (D1 - D0), theta1=90, theta2=180, linewidth=0.6, zorder=4))
    ax.plot([WV, WV - (D1 - D0)], [Y(D1), Y(D1)], color="black", linewidth=1.2, zorder=4)
    if not furniture:
        return r
    r(0.0, 1.3, 0.08, 1.7, fc="#666666", lw_=0.3, z=2)                   # батарея
    r(0.1, W0 + C.WINDOW_W / 2 - 0.275, 0.55, 0.55, label="Т")         # тумба
    r(4.95, 0.0, 1.25, 0.5, label="Ш")
    r(5.1, 1.5, 1.25, 0.5, label="Ш")
    r(N0, B_R - 0.65, 0.65, 0.65, label="ШР")
    for d in DESKS:
        r(*d, fc=GRAY if not light_furn else "#f0f0f0")
    for i, (x, y) in enumerate(CHAIRS):
        r(x, y, CH, CH)
    return r


def dim(ax, p1, p2, text, rot=0, fs=9, ext=(None, None), over=0.1):
    """Размер по ГОСТ 2.307: сплошная размерная линия со стрелками до выносных линий, число над
    ней (у вертикального — слева, снизу вверх). ext — точки объекта, от которых идут выносные
    линии к концам размерной (None — без выносной); выносная выходит за размерную на over."""
    for e, p in zip(ext, (p1, p2)):
        if e is None:
            continue
        dx, dy = p[0] - e[0], p[1] - e[1]
        d = math.hypot(dx, dy) or 1
        ax.plot([e[0], p[0] + dx / d * over], [e[1], p[1] + dy / d * over], color="black",
                linewidth=0.4, zorder=7)
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="<|-|>", mutation_scale=6, linewidth=0.5,
                                 color="black", shrinkA=0, shrinkB=0, zorder=7))
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    if rot == 90:                     # отступ числа от линии — в пунктах, не в единицах рисунка
        ax.annotate(text, (mx, my), xytext=(-2, 0), textcoords="offset points", ha="right",
                    va="center", fontsize=fs, rotation=90, zorder=7)
    else:
        ax.annotate(text, (mx, my), xytext=(0, 1.5), textcoords="offset points", ha="center",
                    va="bottom", fontsize=fs, zorder=7)


def axis_line(ax, a, b):
    """Осевая (штрихпунктирная) линия — по ней ставятся размеры до центров светильников."""
    ax.plot([a[0], b[0]], [a[1], b[1]], color="black", linewidth=0.35, linestyle=(0, (8, 2, 1, 2)),
            zorder=5)


def callout(ax, xy, num, txy, rr=0.17):
    ax.plot([xy[0], txy[0]], [xy[1], txy[1]], color="black", linewidth=0.5, zorder=8)
    ax.add_patch(Circle(txy, rr, facecolor="white", edgecolor="black", linewidth=0.7, zorder=9))
    ax.text(*txy, str(num), ha="center", va="center", fontsize=8.5, zorder=10)


# ======================================================================= план помещения
fig, ax = plt.subplots(figsize=(5.6, 7.6), dpi=250)
ax.set_aspect("equal"); ax.axis("off")
r = room(ax)
ax.add_patch(Rectangle((WV - 0.16, Y(0.28)), 0.16, 0.28, facecolor="black", zorder=5))   # огнетушитель
ax.text(1.5 + DW / 2, Y(DD / 2), "РМ", ha="center", va="center", fontsize=8.5, weight="bold", zorder=5)
x, y = DESKS[MY][0], DESKS[MY][1]
callout(ax, (x + 1.05, Y(0.2)), 1, (2.6, Y(1.7)))                     # стол
callout(ax, (CHAIRS[MY][0] + 0.3, Y(CHAIRS[MY][1] + 0.3)), 2, (1.55, Y(1.9)))   # кресло
callout(ax, (-T / 2, Y(1.6)), 3, (0.95, Y(2.35)))                     # окно
callout(ax, (0.04, Y(2.7)), 4, (0.95, Y(2.85)))                       # батарея
callout(ax, (WV - 0.08, Y(0.14)), 5, (WV - 0.55, Y(0.85)))            # огнетушитель
callout(ax, (WV, Y(1.0)), 6, (WV + 0.55, Y(1.0)))                     # дверь
dim(ax, (0, Y(0) + 0.45), (WV, Y(0) + 0.45), f"{fmt(WV)} м", ext=((0, Y(0) + T), (WV, Y(0) + T)))
dim(ax, (0, Y(LT) - 0.45), (W, Y(LT) - 0.45), f"{fmt(W)} м", ext=((0, Y(B_L) - T), (W, Y(B_R) - T)))
dim(ax, (WV + 0.6, Y(0)), (WV + 0.6, Y(LT)), f"{fmt(B_R)} м", rot=90,
    ext=((WV + T, Y(0)), (W + T, Y(B_R))))
dim(ax, (-0.65, Y(0)), (-0.65, Y(B_L)), f"{fmt(B_L)} м", rot=90, ext=((-T, Y(0)), (-T, Y(B_L))))
ax.text(2.0, Y(5.9), f"S = {fmt(R['S'])} м²", fontsize=10, style="italic", ha="center")
ax.set_xlim(-1.0, WV + 1.4); ax.set_ylim(Y(LT) - 0.8, Y(0) + 0.8)
fig.subplots_adjust(0, 0, 1, 1)
fig.savefig("plan.png")
plt.close(fig)

# ======================================================================= размещение светильников
fig, ax = plt.subplots(figsize=(5.6, 7.6), dpi=250)
ax.set_aspect("equal"); ax.axis("off")
room(ax, light_furn=True)
xs = [R["l_B"] + k * R["L_B"] for k in range(C.ROWS)]
ys = [R["l_A"] + k * R["L_A"] for k in range(R["per_row"])]
for xc in xs:
    for yc in ys:
        ax.add_patch(Rectangle((xc - 0.3, Y(yc) - 0.3), 0.6, 0.6, facecolor="white", edgecolor="black",
                               linewidth=1.0, zorder=6))
        ax.plot([xc - 0.3, xc + 0.3], [Y(yc) - 0.3, Y(yc) + 0.3], color="black", linewidth=0.6, zorder=6)
        ax.plot([xc - 0.3, xc + 0.3], [Y(yc) + 0.3, Y(yc) - 0.3], color="black", linewidth=0.6, zorder=6)
# оси рядов светильников (штрихпунктир) — от них идут размеры до центров
yb, xd = Y(LT) - 0.4, -0.55
for xc in xs:
    axis_line(ax, (xc, Y(0) + 0.1), (xc, yb - 0.1))
for yc in ys:
    axis_line(ax, (xd - 0.1, Y(yc)), (xs[-1] + 0.45, Y(yc)))
dim(ax, (0, yb), (xs[0], yb), f"{fmt(R['l_B'], 2)}", fs=8, ext=((0, Y(B_L) - T), None))
dim(ax, (xs[0], yb), (xs[1], yb), f"{fmt(R['L_B'], 2)}", fs=8)
dim(ax, (xs[1], yb), (W, yb), f"{fmt(R['l_B'], 2)}", fs=8, ext=(None, (W, Y(B_R) - T)))
dim(ax, (xd, Y(0)), (xd, Y(ys[0])), f"{fmt(R['l_A'], 2)}", rot=90, fs=8, ext=((-T, Y(0)), None))
for k in range(R["per_row"] - 1):
    dim(ax, (xd, Y(ys[k])), (xd, Y(ys[k + 1])), f"{fmt(R['L_A'], 2)}", rot=90, fs=8)
dim(ax, (xd, Y(ys[-1])), (xd, Y(B_L)), f"{fmt(R['l_A'], 2)}", rot=90, fs=8, ext=(None, (-T, Y(B_L))))
ax.set_xlim(-1.0, WV + 0.4); ax.set_ylim(Y(LT) - 0.6, Y(0) + 0.4)
fig.subplots_adjust(0, 0, 1, 1)
fig.savefig("lights.png")
plt.close(fig)

# ======================================================================= компоновка рабочего места (вид сбоку)
fig, ax = plt.subplots(figsize=(6.2, 4.4), dpi=250)
ax.set_aspect("equal")
ax.axis("off")
DH = C.DESK_H_MM
SEAT = 450
ED = C.EYE_SCREEN_MM
desk_x0, desk_x1 = 0, 700
INK = "#444444"
# стол
ax.add_patch(Rectangle((desk_x0, DH - 25), desk_x1, 25, facecolor=GRAY, edgecolor="black", linewidth=0.8))
ax.add_patch(Rectangle((desk_x0, 0), 30, DH - 25, facecolor=GRAY, edgecolor="black", linewidth=0.8))
# пространство для ног (как на рисунке компоновки у Ерофеевой): высота LEG_H, глубина LEG_D
LEG_H, LEG_D = C.LEG_SPACE
ax.plot([desk_x1 - LEG_D] * 2, [0, LEG_H], color=WALL, linewidth=0.6, linestyle="--")
ax.plot([desk_x1 - LEG_D, desk_x1], [LEG_H, LEG_H], color=WALL, linewidth=0.6, linestyle="--")
# человек: таз, колено, голеностоп, плечо, шея, голова, локоть, кисть (мм)
hip, knee, ankle = (920, SEAT + 10), (450, SEAT + 30), (440, 9)     # бедро на сиденье, стопа на полу
shoulder, neck_top = (965, 1030), (935, 1110)    # спина откинута на спинку
head_c, head_r = (900, 1195), 90
eye = (835, 1180)
elbow, hand = (880, 775), (620, DH + 40)
# монитор: центр экрана на расстоянии ED от глаз, линия взгляда наклонена на MON_ANGLE
ang = math.radians(C.MON_ANGLE)
scr = (eye[0] - ED * math.cos(ang), eye[1] - ED * math.sin(ang))
# экран: MON_TILT — отклонение верхнего края от пользователя (0 — вертикально)
tl = math.radians(C.MON_TILT)
u, nv = (-math.sin(tl), math.cos(tl)), (math.cos(tl), math.sin(tl))      # вдоль экрана вверх / к пользователю
SL, SW = 155, 15                                                          # полувысота / полутолщина экрана
ax.add_patch(Polygon([(scr[0] + a * SL * u[0] + b * SW * nv[0], scr[1] + a * SL * u[1] + b * SW * nv[1])
                      for a, b in ((-1, -1), (-1, 1), (1, 1), (1, -1))], closed=True, facecolor="black"))
bot = (scr[0] - SL * u[0], scr[1] - SL * u[1])
ax.plot([bot[0], bot[0]], [DH, bot[1]], color="black", linewidth=2)
ax.add_patch(Rectangle((bot[0] - 75, DH), 150, 12, facecolor="black"))
# клавиатура
ax.add_patch(Rectangle((desk_x1 - 280, DH), 230, C.KB_H, facecolor="white", edgecolor="black", linewidth=0.7))
# кресло
ax.add_patch(Rectangle((600, SEAT - 40), 400, 40, facecolor="white", edgecolor="black", linewidth=0.8))
# спинка вплотную к спине: человек сидит, опираясь на неё
ax.add_patch(Polygon([(929, SEAT), (969, SEAT), (1010, SEAT + 520), (970, SEAT + 520)],
                     closed=True, facecolor="white", edgecolor="black", linewidth=0.8))
ax.plot([800, 800], [50, SEAT - 40], color="black", linewidth=2)           # стойка
ax.plot([640, 960], [50, 50], color="black", linewidth=2)                  # крестовина
for xw in (650, 950):                                                     # колёсики на полу
    ax.add_patch(Circle((xw, 22), 22, facecolor="white", edgecolor="black", linewidth=0.8, zorder=2))
for a, b in ((hip, knee), (knee, ankle), (hip, shoulder), (shoulder, neck_top), (shoulder, elbow), (elbow, hand)):
    ax.plot([a[0], b[0]], [a[1], b[1]], color=INK, linewidth=5, solid_capstyle="round")
ax.plot([ankle[0] + 15, ankle[0] - 120], [ankle[1], ankle[1]], color=INK, linewidth=5,
        solid_capstyle="round")                                            # стопа от голеностопа
ax.add_patch(Circle(head_c, head_r, facecolor="white", edgecolor=INK, linewidth=2, zorder=3))
ax.plot(*eye, "o", color="black", markersize=2.5, zorder=4)
# линия взгляда и горизонталь
ax.plot([eye[0], scr[0] + SW * nv[0]], [eye[1], scr[1] + SW * nv[1]], color="black", linewidth=0.7,
        linestyle="-.")
ax.plot([eye[0], scr[0] - 60], [eye[1], eye[1]], color="black", linewidth=0.5, linestyle=":")
ax.text(eye[0] - 190, eye[1] - 50, f"{C.MON_ANGLE}°", fontsize=8.5)
ax.plot([-100, 1420], [0, 0], color="black", linewidth=1.2)
# размеры
dim(ax, (-80, 0), (-80, DH), f"{DH}", rot=90, ext=(None, (desk_x0, DH)), over=25)
dim(ax, (1200, 0), (1200, SEAT), f"{SEAT}", rot=90, ext=(None, (1000, SEAT)), over=25)
dim(ax, (desk_x1 - LEG_D - 60, 0), (desk_x1 - LEG_D - 60, LEG_H), f"{LEG_H}", rot=90, fs=8.5,
    ext=(None, (desk_x1 - LEG_D, LEG_H)), over=25)
dim(ax, (desk_x1 - LEG_D, -75), (desk_x1, -75), f"{LEG_D}", fs=8.5,
    ext=((desk_x1 - LEG_D, 0), (desk_x1, DH - 25)), over=25)
ax.text((scr[0] + eye[0]) / 2 - 90, (scr[1] + eye[1]) / 2 + 10, f"{ED}", ha="center", va="bottom",
        fontsize=9, rotation=math.degrees(ang))
dim(ax, (1340, 0), (1340, eye[1]), "1130–1220", rot=90, ext=(None, (head_c[0] + head_r + 15, eye[1])), over=25)
ax.set_xlim(-180, 1420)
ax.set_ylim(-130, head_c[1] + head_r + 60)
fig.subplots_adjust(0, 0, 1, 1)
fig.savefig("layout.png")
plt.close(fig)

# ======================================================================= зоны досягаемости (вид сверху)
fig, ax = plt.subplots(figsize=(6.2, 4.0), dpi=250)
ax.set_aspect("equal")
ax.axis("off")
DWm, DDm = C.DESK_MM
ax.add_patch(Rectangle((0, 0), DWm, DDm, facecolor="#f2f2f2", edgecolor="black", linewidth=0.9))
shoulders = [(DWm / 2 - 200, -150), (DWm / 2 + 200, -150)]   # плечевые суставы сидящего, мм
zones = [(650, "#e8e8e8"), (500, "#cfcfcf"), (350, "#b0b0b0")]
for rad, col in zones:
    for k, (sx, sy) in enumerate(shoulders):
        ax.add_patch(Wedge((sx, sy), rad, 20, 160, facecolor=col, edgecolor="none", alpha=0.75, zorder=1))
ax.add_patch(Rectangle((0, 0), DWm, DDm, facecolor="none", edgecolor="black", linewidth=0.9, zorder=3))
# монитор, клавиатура, мышь, документы
ax.add_patch(Rectangle((DWm / 2 - 270, 520), 540, 40, facecolor="black", zorder=4))
ax.add_patch(Rectangle((DWm / 2 - 220, 80), 440, 150, facecolor="white", edgecolor="black", linewidth=0.8, zorder=4))
ax.add_patch(Rectangle((DWm / 2 + 300, 110), 60, 100, facecolor="white", edgecolor="black", linewidth=0.8, zorder=4))
ax.add_patch(Rectangle((140, 120), 230, 300, facecolor="white", edgecolor="black", linewidth=0.6,
                       linestyle="--", zorder=4))
ax.add_patch(Rectangle((DWm / 2 - 130, -480), 260, 300, facecolor="white", edgecolor="black", linewidth=0.8, zorder=2))
callout(ax, (DWm / 2 + 200, 540), 1, (DWm / 2 + 420, 640), rr=38)
callout(ax, (DWm / 2 - 100, 155), 2, (DWm / 2 - 120, 330), rr=38)
callout(ax, (DWm / 2 + 330, 160), 3, (DWm / 2 + 470, 330), rr=38)
callout(ax, (255, 330), 4, (230, 600), rr=38)
callout(ax, (DWm / 2 + 130, -330), 5, (DWm / 2 + 300, -380), rr=38)
for rad, lab in ((350, "А"), (500, "Б"), (650, "В")):
    sx, sy = shoulders[0]
    ax.text(sx + (rad - 55) * math.cos(math.radians(152)), sy + (rad - 55) * math.sin(math.radians(152)), lab,
            fontsize=9.5, weight="bold", ha="center", va="center", zorder=5)
dim(ax, (0, -560), (DWm, -560), f"{DWm}", fs=8.5, ext=((0, 0), (DWm, 0)), over=25)
dim(ax, (DWm + 90, 0), (DWm + 90, DDm), f"{DDm}", rot=90, fs=8.5, ext=((DWm, 0), (DWm, DDm)), over=25)
ax.set_xlim(-120, DWm + 160)
ax.set_ylim(-640, DDm + 160)
fig.subplots_adjust(0, 0, 1, 1)
fig.savefig("reach.png")
plt.close(fig)
print("saved plan.png, lights.png, layout.png, reach.png")
