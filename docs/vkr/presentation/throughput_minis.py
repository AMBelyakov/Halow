# -*- coding: utf-8 -*-
"""Мини-графики «было → стало» для слайда 10 (27.10, пользователь: «сократи без потери смысла, может графики»).
Числа — из ВКР и журнала halow_link_debug.md: UART (подраздел 3.3, табл. предела интерфейса и приёма UART),
RTS/CTS (опыт 29.09, var0929r, видео Q80), кодер (3.3), граница MCS и FEC (табл. парных опытов).
Запуск: python throughput_minis.py -> tp_iface.png, tp_radio.png, tp_video.png рядом со скриптом.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BLUE, GREY, INK = "#2A78D6", "#B9BEC7", "#14213D"
plt.rcParams.update({"font.family": "Arial"})


def minis(name, rows):
    """rows: (подпись, было, стало, текст было, текст стало, меньше_лучше)."""
    fig = plt.figure(figsize=(5.2, 2.2), dpi=200)
    n = len(rows)
    for i, (lab, a, b, ta, tb, _lower) in enumerate(rows):
        ax = fig.add_axes([0.02, 0.98 - (i + 1) * 0.96 / n, 0.96, 0.96 / n - 0.03])
        ax.set_xlim(0, max(a, b) * 1.55)
        ax.set_ylim(-0.5, 2.6)
        ax.axis("off")
        ax.text(0, 2.15, lab, fontsize=15, color=INK, va="center", weight="bold")
        for y, v, t, c in ((1.15, a, ta, GREY), (0.2, b, tb, BLUE)):
            ax.barh(y, v, height=0.7, color=c)
            ax.text(v + max(a, b) * 0.03, y, t, fontsize=15, color=INK if c == GREY else BLUE,
                    va="center", weight="bold" if c == BLUE else "normal")
    fig.savefig(os.path.join(HERE, name), facecolor="white")
    plt.close(fig)


minis("tp_iface.png", [
    ("предел UART, Мбит/с", 0.17, 1.8, "0,17", "1,8", False),
    ("потери байтов на входе модуля, %", 89.5, 0.0, "89,5", "0", True),
])
minis("tp_radio.png", [
    ("видео, кбит/с", 282, 618, "282", "618", False),
    ("задержка, мс", 611, 134, "611", "134", True),
])
minis("tp_video.png", [
    ("сжатие кадра 320×240, мс", 150, 65, "150", "62–68", True),
    ("граница MCS: скорость, кбит/с", 455, 775, "370–540", "740–800", False),
    ("FEC + досылка: потери кадров, %", 11.3, 2.75, "10–12", "2–3", True),
])
print("ok")
