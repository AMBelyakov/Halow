"""Оформление слайдов по образцу презентации кафедры 402 (29.10, пользователь: «оформлено очень круто —
возникнут вопросы, сделай как в презентации Орлова»): белый фон, шрифт Times, заголовки по центру
жирным, таблицы с синей шапкой и полосами, подписи рисунков жирным, номер слайда в рамке справа внизу,
без карточек с тенями, скруглений и значков. Содержание и текст выступления не меняются.
Проход идемпотентен: его можно применять и к слайдам, которые пользователь правит в показе (LIVE)."""
import re

FONT = "'Tinos', 'Times New Roman', serif"
HEAD_BG, ROW_A, ROW_B, ROW_HL = "#4F81BD", "#D0D8E8", "#E9EDF4", "#B4C6E7"

# цвет старой темы → цвет образца (без учёта регистра)
COLORS = {
    "#14213D": "#000000",   # основной текст
    "#4A5568": "#000000",   # второстепенный текст
    "#5F6673": "#404040",   # подписи, примечания
    "#FDFCFA": "#FFFFFF",   # карточки
    "#F7F6F2": "#FFFFFF",   # фон слайда
    "#ECEAE3": "#FFFFFF",   # второй фон слайда
    "#E0DDD4": "#A6A6A6",   # рамки
}


def _tables(html):
    def one(m):
        t = m.group(0)
        rows = t.split("<tr")
        out, k = [rows[0]], 0
        for r in rows[1:]:
            if r.startswith(' style="background:#E4E1D8"'):          # шапка
                r = r.replace("#E4E1D8", HEAD_BG, 1)
                r = re.sub(r'<th style="([^"]*)"', lambda x: '<th style="' + re.sub(r"color:#[0-9A-Fa-f]{6};?\s*", "", x.group(1)).rstrip("; ") + '; color:#FFFFFF"', r)
                r = r.replace("<th>", '<th style="color:#FFFFFF">')
            elif r.startswith(' style="background:#FDFCFA"'):
                r = r.replace("#FDFCFA", (ROW_A, ROW_B)[k % 2], 1)
                k += 1
            elif r.startswith(' style="background:#E4ECF7"'):        # выделенная строка
                r = r.replace("#E4ECF7", ROW_HL, 1)
                k += 1
            out.append(r)
        return "<tr".join(out)
    return re.sub(r"<table.*?</table>", one, html, flags=re.S)


def academic(html):
    # слайд-заявление на синей заливке (whyexp из показа) — белый, как остальные
    if re.search(r"padding:128px 128px 160px; background:#1f5fae", html, flags=re.I):
        html = re.sub(r"padding:128px 128px 160px; background:#1f5fae", "padding:128px 128px 160px; background:#FFFFFF", html, flags=re.I)
        html = re.sub(r"background:#2c6bb8; border-radius:\w+", "background:#FFFFFF; border:1px solid #A6A6A6; border-radius:0", html, flags=re.I)
        html = re.sub(r"color:#(?:e3ecf8|ffffff)", "color:#000000", html, flags=re.I)
    html = _tables(html)
    html = html.replace("'IBM Plex Sans', Arial, sans-serif", FONT)
    for a, b in COLORS.items():
        html = re.sub(re.escape(a), b, html, flags=re.I)
    # без скруглений у карточек, плашек и шапок (кружки с номерами шагов остаются)
    html = re.sub(r"border-radius:(?:8px 8px 0 0|10px|12px|14px|16px)", "border-radius:0", html)
    # без значков
    html = re.sub(r"<x-icon[^>]*></x-icon>", "", html)
    # заголовки слайдов — по центру, жирным
    def h2(m):
        st = m.group(2).replace("font-size:64px", "font-size:52px").replace("font-weight:600", "font-weight:700")
        if "text-align" not in st:
            st += "; text-align:center"
        return f"<h2{m.group(1)} style=\"{st}\">"
    html = re.sub(r'<h2([^>]*?) style="([^"]*)">', h2, html)
    # подписи рисунков — жирным, чёрным
    def cap(m):
        st = m.group(1).replace("#404040", "#000000")
        if "font-weight" not in st:
            st += "; font-weight:700"
        return f'<p style="{st}">Рисунок'
    html = re.sub(r'<p style="([^"]*)">Рисунок', cap, html)
    # номер слайда — в рамке справа внизу
    html = re.sub(r'<p([^>]*?) style="[^"]*">Wi-Fi HaLow для БПЛА · (\d+) / \d+</p>',
                  lambda m: (f'<p{m.group(1)} style="position:absolute; right:64px; bottom:40px; width:72px; '
                             f'font-family:{FONT}; font-size:28px; line-height:1.4; color:#000000; '
                             f'text-align:center; border:1px solid #000000">{m.group(2)}</p>'), html)
    return html
