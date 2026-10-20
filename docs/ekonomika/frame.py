# -*- coding: utf-8 -*-
"""Рамка и основная надпись листов пояснительной записки (ГОСТ 2.104, формы 2 и 2а).

Таблицы штампов взяты из рамок кафедры (ramki/Ramka_A4_s_bolshim_shtampom.doc и
..._s_malym_shtampom.doc, 13.10.2026) и лежат в ramki/stamp_big.xml, stamp_small.xml.

Как устроено:
- контур рамки (поле подшивки 20 мм, остальные 5 мм) — прямоугольник VML в верхнем
  колонтитуле, привязанный к странице, за текстом;
- основная надпись — обычная таблица в нижнем колонтитуле: на первом листе части (если
  big_first) — форма 2 высотой 40 мм, на остальных — форма 2а высотой 15 мм. Нижний колонтитул
  выше поля сам отодвигает текст, поэтому текст на штамп не налезает;
- номер листа — поле PAGE со сквозным началом (pgNumType start), «Листов» — из frame.json.

Данные надписи (обозначение документа, фамилии, группа, начальные листы частей) —
docs/vkr/frame.json.
"""
import copy
import json
import os

from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Mm

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_FILE = os.path.normpath(os.path.join(HERE, "..", "vkr", "frame.json"))
FONT = "Arial"                          # 20.10: как у Ерофеевой (курсив Arial), а не GOST type B
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FRAME_W_MM = 185                        # 210 − 20 − 5
FRAME_H_MM = 287                        # 297 − 5 − 5
EXTRA_TW = round(FRAME_W_MM / 25.4 * 1440) - 10348   # штамп рамок — 182,5 мм; добираем до 185


def load_cfg():
    with open(CFG_FILE, encoding="utf-8") as f:
        return json.load(f)


def _stamp(kind):
    with open(os.path.join(HERE, "ramki", f"stamp_{kind}.xml"), encoding="utf-8") as f:
        xml = f.read()
    if "xmlns:w=" not in xml.split(">", 1)[0]:
        xml = xml.replace("<w:tbl", f'<w:tbl xmlns:w="{W_NS}"', 1)
    return parse_xml(xml)


def _widen(tbl, col):
    """Расширяет столбец col (графа наименования) так, чтобы штамп занял 185 мм."""
    grid = tbl.findall(f"{qn('w:tblGrid')}/{qn('w:gridCol')}")
    grid[col].set(qn("w:w"), str(int(grid[col].get(qn("w:w"))) + EXTRA_TW))
    for tr in tbl.findall(qn("w:tr")):
        c = 0
        for tc in tr.findall(qn("w:tc")):
            pr = tc.find(qn("w:tcPr"))
            span = pr.find(qn("w:gridSpan")) if pr is not None else None
            n = int(span.get(qn("w:val"))) if span is not None else 1
            if c <= col < c + n:
                w = pr.find(qn("w:tcW"))
                w.set(qn("w:w"), str(int(w.get(qn("w:w"))) + EXTRA_TW))
            c += n


def _cells(tbl):
    """Ячейки по строкам: [(первый столбец сетки, tc), ...]."""
    rows = []
    for tr in tbl.findall(qn("w:tr")):
        c, row = 0, []
        for tc in tr.findall(qn("w:tc")):
            pr = tc.find(qn("w:tcPr"))
            span = pr.find(qn("w:gridSpan")) if pr is not None else None
            row.append((c, tc))
            c += int(span.get(qn("w:val"))) if span is not None else 1
        rows.append(row)
    return rows


def _fmt_all(tbl):
    """Шрифт ГОСТ, курсив, без отступов и интервалов — во всех ячейках (у рамок стиль a3)."""
    for p in tbl.iter(qn("w:p")):
        ppr = p.find(qn("w:pPr"))
        if ppr is None:
            ppr = OxmlElement("w:pPr")
            p.insert(0, ppr)
        for tag in ("w:pStyle", "w:ind", "w:spacing"):
            for e in ppr.findall(qn(tag)):
                ppr.remove(e)
        ind = OxmlElement("w:ind")
        ind.set(qn("w:firstLine"), "0")
        ind.set(qn("w:left"), "0")
        sp = OxmlElement("w:spacing")
        sp.set(qn("w:before"), "0")
        sp.set(qn("w:after"), "0")
        sp.set(qn("w:line"), "240")
        sp.set(qn("w:lineRule"), "auto")
        ppr.insert(0, ind)
        ppr.insert(0, sp)
        for r in p.findall(qn("w:r")):
            _rfmt(r)


def _top_line(tbl):
    """Верхняя линия основной надписи (в рамках кафедры её даёт контур рамки, у нас — штамп)."""
    tr = tbl.find(qn("w:tr"))
    for tc in tr.findall(qn("w:tc")):
        pr = tc.find(qn("w:tcPr"))
        b = pr.find(qn("w:tcBorders"))
        if b is None:
            b = OxmlElement("w:tcBorders")
            pr.insert(1, b)
        for e in b.findall(qn("w:top")):
            b.remove(e)
        top = OxmlElement("w:top")
        for k, v in (("w:val", "single"), ("w:sz", "18"), ("w:space", "0"), ("w:color", "auto")):
            top.set(qn(k), v)
        b.insert(0, top)


def _rfmt(r, size=None):
    rpr = r.find(qn("w:rPr"))
    if rpr is None:
        rpr = OxmlElement("w:rPr")
        r.insert(0, rpr)
    for tag in ("w:rFonts", "w:i"):
        for e in rpr.findall(qn(tag)):
            rpr.remove(e)
    f = OxmlElement("w:rFonts")
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        f.set(qn(a), FONT)
    rpr.insert(0, f)
    rpr.insert(1, OxmlElement("w:i"))
    if size:
        for e in rpr.findall(qn("w:sz")) + rpr.findall(qn("w:szCs")):
            rpr.remove(e)
        for tag in ("w:sz", "w:szCs"):
            e = OxmlElement(tag)
            e.set(qn("w:val"), str(size * 2))
            rpr.append(e)


def _put(tc, text=None, size=9, align="center", field=None):
    """Пишет текст (или поле PAGE) в ячейку, заменяя содержимое."""
    p = tc.find(qn("w:p"))
    for r in p.findall(qn("w:r")):
        p.remove(r)
    ppr = p.find(qn("w:pPr"))
    for e in ppr.findall(qn("w:jc")):
        ppr.remove(e)
    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), align)
    ppr.append(jc)
    if field:
        for kind, txt in (("begin", None), (None, field), ("end", None)):
            r = OxmlElement("w:r")
            _rfmt(r, size)
            if kind:
                e = OxmlElement("w:fldChar")
                e.set(qn("w:fldCharType"), kind)
            else:
                e = OxmlElement("w:instrText")
                e.set(qn("xml:space"), "preserve")
                e.text = f" {txt} "
            r.append(e)
            p.append(r)
        return
    r = OxmlElement("w:r")
    _rfmt(r, size)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    p.append(r)


def big_stamp(cfg):
    tbl = _stamp("big")
    _widen(tbl, 5)
    _top_line(tbl)
    _fmt_all(tbl)
    rows = _cells(tbl)
    at = lambda r, c: dict(rows[r])[c]                       # noqa: E731
    _put(at(0, 5), cfg["code"], size=16)
    for r, key in ((3, "razrab"), (4, "prov"), (6, "nkontr"), (7, "utv")):
        _put(at(r, 2), cfg.get(key, ""), align="left")
    _put(at(3, 5), cfg["title"], size=12)
    _put(at(4, 7), cfg.get("litera", "У"))
    _put(at(4, 9), field="PAGE")
    _put(at(4, 10), str(cfg["total"]))
    _put(at(5, 6), cfg["org"], size=14)
    return tbl


def small_stamp(cfg):
    tbl = _stamp("small")
    _widen(tbl, 5)
    _top_line(tbl)
    _fmt_all(tbl)
    rows = _cells(tbl)
    at = lambda r, c: dict(rows[r])[c]                       # noqa: E731
    _put(at(0, 5), cfg["code"], size=16)
    _put(at(1, 6), field="PAGE", size=11)
    return tbl


def _neg_indent(tbl, left_margin_mm):
    """Сдвигает штамп влево до линии рамки (поле подшивки 20 мм)."""
    ppr = tbl.find(qn("w:tblPr"))
    for e in ppr.findall(qn("w:tblInd")) + ppr.findall(qn("w:jc")):
        ppr.remove(e)
    ind = OxmlElement("w:tblInd")
    ind.set(qn("w:w"), str(-round((left_margin_mm - 20) / 25.4 * 1440)))
    ind.set(qn("w:type"), "dxa")
    ppr.append(ind)


def _tiny_par(height_tw):
    """Пустой абзац заданной высоты (промежуток над штампом / обязательный абзац после таблицы)."""
    p = OxmlElement("w:p")
    ppr = OxmlElement("w:pPr")
    sp = OxmlElement("w:spacing")
    sp.set(qn("w:before"), "0")
    sp.set(qn("w:after"), "0")
    sp.set(qn("w:line"), str(height_tw))
    sp.set(qn("w:lineRule"), "exact")
    ind = OxmlElement("w:ind")
    ind.set(qn("w:firstLine"), "0")
    rpr = OxmlElement("w:rPr")
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "2")
    rpr.append(sz)
    ppr.extend([sp, ind, rpr])
    p.append(ppr)
    return p


def _rect_run():
    """Контур рамки: прямоугольник от линии подшивки 20 мм, остальные поля 5 мм."""
    pt = lambda mm: f"{mm / 25.4 * 72:.2f}pt"                # noqa: E731
    return parse_xml(
        f'<w:r xmlns:w="{W_NS}" xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:o="urn:schemas-microsoft-com:office:office"><w:pict>'
        f'<v:rect id="vkr_frame" o:allowincell="f" filled="f" strokeweight="1.5pt" style="'
        f"position:absolute;margin-left:{pt(20)};margin-top:{pt(5)};width:{pt(FRAME_W_MM)};"
        f"height:{pt(FRAME_H_MM)};z-index:-251657216;mso-position-horizontal-relative:page;"
        'mso-position-vertical-relative:page"/></w:pict></w:r>')


def _fill_header(hdr):
    p = hdr.paragraphs[0]
    p.paragraph_format.first_line_indent = Mm(0)
    p._p.append(_rect_run())


def _fill_footer(ftr, tbl, left_margin_mm):
    el = ftr._element
    for child in list(el):
        el.remove(child)
    _neg_indent(tbl, left_margin_mm)
    el.append(_tiny_par(170))           # 3 мм между текстом и штампом
    el.append(tbl)
    el.append(_tiny_par(20))            # Word требует абзац после таблицы


def apply(section, part, big_first=None):
    """Рамка на все листы раздела документа. part — ключ в frame.json["start"]."""
    cfg = load_cfg()
    if big_first is None:
        big_first = part in cfg.get("big_first", [])
    section.header_distance = Mm(5)
    section.footer_distance = Mm(5)
    section.bottom_margin = Mm(25)
    section.different_first_page_header_footer = bool(big_first)
    left = section.left_margin.mm
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False
    _fill_header(section.header)
    _fill_footer(section.footer, small_stamp(cfg), left)
    if big_first:
        section.first_page_header.is_linked_to_previous = False
        section.first_page_footer.is_linked_to_previous = False
        _fill_header(section.first_page_header)
        _fill_footer(section.first_page_footer, big_stamp(cfg), left)
    sp = section._sectPr
    for e in sp.findall(qn("w:pgNumType")):
        sp.remove(e)
    pg = OxmlElement("w:pgNumType")
    pg.set(qn("w:start"), str(cfg["start"][part]))
    sp.append(pg)
