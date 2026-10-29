# -*- coding: utf-8 -*-
"""Сборка всей ВКР: основная часть, глава 4 (экономика), глава 5 (охрана труда).

1. Собирает главы и узнаёт, какие источники каждая цитирует (cites/*.json).
2. Строит сквозную нумерацию: сначала основная часть, затем новые источники главы 4,
   затем главы 5 — и пишет её в sources_order.json.
3. Пересобирает главы с окончательными номерами (общий список — в конце основной части).
4. Считает объём для реферата (страницы — через PDF LibreOffice, а без него — через Word,
   рисунки, таблицы, источники) в volume.json; через Word же — начальные листы частей и
   «Листов» для рамок (frame.json), затем пересобирает главы.

Запуск: python3 docs/vkr/build_all.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from docx import Document

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.dirname(HERE)
PARTS = [  # (имя в cites/, папка, скрипт, docx)
    ("main", HERE, "build_main.py", "Osnovnaya_chast_HaLow.docx"),
    ("econ", os.path.join(DOCS, "ekonomika"), "build_docx.py", "Ekonomicheskaya_chast_HaLow.docx"),
    ("ot", os.path.join(DOCS, "ohrana_truda"), "build_ot.py", "Okhrana_truda_HaLow.docx"),
]
ORDER_FILE = os.path.join(HERE, "sources_order.json")
VOLUME_FILE = os.path.join(HERE, "volume.json")
FRAME_FILE = os.path.join(HERE, "frame.json")
TOC_FILE = os.path.join(HERE, "toc.json")       # содержание всей ПЗ: [уровень, заголовок, лист]
FRONT_SHEETS = 2          # титульный лист и задание — листы 1–2, «Содержание» — лист 3


def build(only=None):
    for name, d, script, _ in PARTS:
        if only and name not in only:
            continue
        r = subprocess.run([sys.executable, script], cwd=d, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"{script}: ошибка\n{r.stdout}\n{r.stderr}")
        print(f"  {script}: {r.stdout.strip().splitlines()[-1]}")


def cites(name):
    with open(os.path.join(HERE, "cites", f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


LOCAL = {"ot"}   # 29.10: у раздела 5 своя нумерация и свой список (как в образце кафедры)


def global_order():
    order = {}
    for name, *_ in PARTS:
        if name in LOCAL:
            continue
        for k in cites(name):
            order.setdefault(k, len(order) + 1)
    return order


def all_sources():
    """Число разных источников ВКР — для реферата: сквозной список и списки разделов."""
    return len({k for name, *_ in PARTS for k in cites(name)})


def pages(docx_path):
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", tmp, docx_path],
                       capture_output=True, check=True, timeout=300)
        pdf = os.path.join(tmp, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
        info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True, check=True).stdout
    return int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))


def word_available():
    try:
        import win32com.client  # noqa: F401
        return True
    except ImportError:
        return False


def word_layout():
    """Листы частей ПЗ по вёрстке Word (оглавление обновляется, как при печати):
    main — от «Содержания» до конца главы 3, tail — заключение и источники."""
    import win32com.client
    out = {}
    w = win32com.client.DispatchEx("Word.Application")
    w.Visible, w.DisplayAlerts = False, 0
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for name, d, _, docx in PARTS:
                src = os.path.join(tmp, docx)
                shutil.copy(os.path.join(d, docx), src)
                doc = w.Documents.Open(src, False, True, False)
                for toc in doc.TablesOfContents:
                    toc.Update()
                doc.Repaginate()
                # ComputeStatistics с колонтитулами-таблицами завышает число страниц вдвое;
                # Information(4) — страниц в документе, Information(3) — физическая страница
                total = doc.Content.Information(4)
                # заголовки 1–2 уровня с номером листа (с учётом начального листа части)
                for par in doc.Paragraphs:
                    lvl = par.OutlineLevel
                    if lvl > 2:
                        continue
                    text = par.Range.Text.strip()
                    if not text or text == "Содержание":
                        continue
                    part = name if (name != "main" or par.Range.Sections(1).Index == 1) else "tail"
                    out.setdefault("toc", {}).setdefault(part, []).append(
                        [lvl, text, par.Range.Information(1)])
                if name == "main":
                    out["main"] = doc.Sections(1).Range.Information(3)
                    out["tail"] = total - out["main"]
                else:
                    out[name] = total
                doc.Close(False)
    finally:
        w.Quit()
    return out


def captions(docx_path):
    doc = Document(docx_path)
    figs = tabs = 0
    for p in doc.paragraphs:
        t = p.text.strip()
        if re.match(r"Рисунок \d+\.\d+ [–-] ", t):
            figs += 1
        elif re.match(r"Таблица \d+\.\d+ [–-] ", t):
            tabs += 1
    return figs, tabs


def main():
    print("проход 1: главы и их источники")
    build()
    order = global_order()
    with open(ORDER_FILE, "w", encoding="utf-8") as f:
        json.dump(order, f, ensure_ascii=False, indent=1)
    print("проход 2: сквозная нумерация")
    build()
    if global_order() != order:
        sys.exit("порядок источников не сошёлся после второго прохода")

    if shutil.which("soffice") and shutil.which("pdfinfo"):
        for attempt in range(2):        # число страниц основной части зависит от самого реферата
            total_pages, figs, tabs = 0, 0, 0
            for name, d, _, docx in PARTS:
                path = os.path.join(d, docx)
                total_pages += pages(path)
                f_, t_ = captions(path)
                figs, tabs = figs + f_, tabs + t_
            vol = {"pages": total_pages, "figures": figs, "tables": tabs, "sources": all_sources()}
            try:
                with open(VOLUME_FILE, encoding="utf-8") as f:
                    old = json.load(f)
            except FileNotFoundError:
                old = None
            if vol == old:
                break
            with open(VOLUME_FILE, "w", encoding="utf-8") as f:
                json.dump(vol, f, ensure_ascii=False, indent=1)
            print(f"проход 3: объём {vol}")
            build(only={"main"})
    elif word_available():
        for attempt in range(3):        # номера листов и объём зависят от самой вёрстки
            lay = word_layout()
            cfg = json.load(open(FRAME_FILE, encoding="utf-8"))
            start = {"main": FRONT_SHEETS + 1}
            start["econ"] = start["main"] + lay["main"]
            start["ot"] = start["econ"] + lay["econ"]
            start["tail"] = start["ot"] + lay["ot"]
            total = start["tail"] + lay["tail"] - 1
            figs = tabs = 0
            for name, d, _, docx in PARTS:
                f_, t_ = captions(os.path.join(d, docx))
                figs, tabs = figs + f_, tabs + t_
            vol = {"pages": total, "figures": figs, "tables": tabs, "sources": all_sources()}
            try:
                old = json.load(open(VOLUME_FILE, encoding="utf-8"))
            except FileNotFoundError:
                old = None
            toc = [e for part in ("main", "econ", "ot", "tail") for e in lay["toc"].get(part, [])]
            try:
                old_toc = json.load(open(TOC_FILE, encoding="utf-8"))
            except FileNotFoundError:
                old_toc = None
            with open(TOC_FILE, "w", encoding="utf-8") as f:
                json.dump(toc, f, ensure_ascii=False, indent=0)
            if (cfg.get("start") == start and cfg.get("total") == total and vol == old
                    and toc == old_toc):
                break
            cfg["start"], cfg["total"] = start, total
            with open(FRAME_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=1)
            with open(VOLUME_FILE, "w", encoding="utf-8") as f:
                json.dump(vol, f, ensure_ascii=False, indent=1)
            print(f"проход {3 + attempt}: листы {start}, всего {total}; объём {vol}; "
                  f"в содержании {len(toc)} строк")
            build()
    else:
        print("нет soffice/pdfinfo и Word — объём в реферате и листы в штампах не обновлены")
    print(f"готово: источников в ВКР {all_sources()}, в сквозном списке {len(order)}")


if __name__ == "__main__":
    main()
