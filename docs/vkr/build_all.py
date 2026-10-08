# -*- coding: utf-8 -*-
"""Сборка всей ВКР: основная часть, глава 4 (экономика), глава 5 (охрана труда).

1. Собирает главы и узнаёт, какие источники каждая цитирует (cites/*.json).
2. Строит сквозную нумерацию: сначала основная часть, затем новые источники главы 4,
   затем главы 5 — и пишет её в sources_order.json.
3. Пересобирает главы с окончательными номерами (общий список — в конце основной части).
4. Считает объём для реферата (страницы — через PDF LibreOffice, рисунки, таблицы,
   источники) в volume.json и пересобирает основную часть.

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


def global_order():
    order = {}
    for name, *_ in PARTS:
        for k in cites(name):
            order.setdefault(k, len(order) + 1)
    return order


def pages(docx_path):
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", tmp, docx_path],
                       capture_output=True, check=True, timeout=300)
        pdf = os.path.join(tmp, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
        info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True, check=True).stdout
    return int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))


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
            vol = {"pages": total_pages, "figures": figs, "tables": tabs, "sources": len(order)}
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
    else:
        print("нет soffice/pdfinfo — объём в реферате не обновлён")
    print(f"готово: источников в ВКР {len(order)}")


if __name__ == "__main__":
    main()
