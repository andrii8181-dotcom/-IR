# test_sad_clip.py – форматоване копіювання таблиць (HTML для Word/Excel)
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sad_clip as C
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg)
    if not c: FAIL.append(msg)
H = ["Рік", "tсер, °C", "Опади <мм>", "Умови"]
R = [["2021", "15,5", "465", "достатньо волого"], ["2022 & 2023", "15,6", "469", "надмірно <волого>"], ["2024", "", "480", None]]
print("== 1. HTML-таблиця")
h = C.build_html_table(H, R, fills=["#e2efda", None, "#ddebf7"])
check(h.count("<tr>") == 4 and h.count("<th") == 4 and h.count("<td") == 12, "4 рядки (заголовок + 3), 4 заголовки, 12 комірок")
check('border="1"' in h and "border-collapse:collapse" in h and h.count("border:1px solid #000000") >= 17, "сітка: border=1, об'єднані рамки, рамка в кожній комірці й заголовку")
check("Опади &lt;мм&gt;" in h and "2022 &amp; 2023" in h and "надмірно &lt;волого&gt;" in h, "спецсимволи <, >, & екрановано")
check("background:#e2efda" in h and "background:#ddebf7" in h and h.count("background:#e2efda") == 4, "заливка рядка застосована до всіх комірок рядка; рядок без кольору – без заливки")
check("background:#D9E2F3" in h and "font-weight:bold" in h, "заголовок виділено")
check(re.search(r"<td[^>]*text-align:left;[^>]*>2021", h) is not None and re.search(r"<td[^>]*text-align:center;[^>]*>15,5", h) is not None, "перший стовпець ліворуч, числа по центру")
check("</td><td" in h and "None" not in h and "<td" in h, "порожні значення (None, '') не перетворюються на текст «None»")
hc = C.build_html_table(H, R, fills=["#e2efda", None, "#ddebf7"], cell_fills=[{1: "#ff0000"}, {3: "#00ff00"}, {}])
check(hc.count("background:#ff0000") == 1 and hc.count("background:#e2efda") == 3 and hc.count("background:#00ff00") == 1 and hc.count("background:#ddebf7") == 4,
      "заливка окремих клітинок має перевагу над кольором рядка; решта клітинок рядка зберігає колір рядка")
check(C.build_html_table(H, R, cell_fills=[{}, {}, {}]).count("background:") == 4 and "background:#" not in C.build_html_table(H, R).replace("#D9E2F3", ""), "без заливок лише заголовок має фон")
print("\n== 2. Формат буфера CF_HTML")
d = C.cf_html(h)
hd, frag = C.parse_cf_html(d)
check(frag == h, "за зміщеннями StartFragment–EndFragment отримуємо рівно HTML-таблицю")
check(hd["StartHTML"] == d.index(b"<html>") and hd["EndHTML"] == len(d), "StartHTML вказує на <html>, EndHTML – на кінець даних")
check(d.startswith(b"Version:0.9\r\n") and re.fullmatch(rb"Version:0.9\r\nStartHTML:\d{10}\r\nEndHTML:\d{10}\r\nStartFragment:\d{10}\r\nEndFragment:\d{10}\r\n", d[:d.index(b"<html>")]),
      "заголовок: Version:0.9 і чотири 10-цифрові зміщення")
cyr = C.cf_html(C.build_html_table(["Показник"], [["Температура, °C – Ґ є ї"]]))
hc, fc = C.parse_cf_html(cyr)
check("Температура, °C – Ґ є ї" in fc and hc["EndFragment"] - hc["StartFragment"] == len(fc.encode("utf-8")) > len(fc), "кирилиця: зміщення рахуються в БАЙТАХ UTF-8, а не в символах")
print("\n== 3. Копіювання за межами Windows (повернення до тексту)")
class FakeW:
    def __init__(self): self.buf = None
    def clipboard_clear(self): self.buf = ""
    def clipboard_append(self, t): self.buf += t
w = FakeW(); res = C.copy_table(w, H, R)
if sys.platform != "win32":
    check(res == "text" and w.buf.split("\n")[0] == "Рік\ttсер, °C\tОпади <мм>\tУмови" and w.buf.count("\n") == 3, "поза Windows: копіюється TSV-текст, повертається 'text'")
w2 = FakeW(); C.copy_table(w2, H, R, tsv="власний\ttsv") if sys.platform != "win32" else None
if sys.platform != "win32": check(w2.buf == "власний\ttsv", "можна передати власний текст TSV (десяткова кома тощо)")
print("\n" + "=" * 56)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ КОПІЮВАННЯ ПРОЙДЕНО")
