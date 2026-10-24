# sad_clip.py – S.A.D. v2.1: копіювання таблиць у буфер обміну так, щоб у Word/Excel зберігалася СІТКА таблиці
# -*- coding: utf-8 -*-
"""
Звичайний текстовий буфер (TSV) вставляється у Word як рядки без рамок. Щоб у Word з'являлася таблиця із сіткою,
у буфер додатково кладуть HTML-фрагмент у форматі «HTML Format» (CF_HTML). Це можливо лише в Windows (Win32 API);
в інших системах копіюється текст (TSV), а таблицю із сіткою дає експорт у Word/Excel.
"""
import sys
from html import escape


def build_html_table(headers, rows, fills=None, font="Times New Roman", size_pt=11, header_fill="#D9E2F3", cell_fills=None):
    """HTML-таблиця з тонкою чорною сіткою. fills – список кольорів (або None) для кожного рядка; cell_fills – список словників
    {індекс_стовпця: колір} для окремих клітинок (має перевагу над кольором рядка)."""
    cell = f"border:1px solid #000000;padding:2px 6px;font-family:'{font}';font-size:{size_pt}pt;"
    out = [f'<table border="1" cellspacing="0" cellpadding="3" style="border-collapse:collapse;border:1px solid #000000;">']
    out.append("<tr>" + "".join(f'<th style="{cell}background:{header_fill};text-align:center;font-weight:bold;">{escape(str(h))}</th>' for h in headers) + "</tr>")
    for i, row in enumerate(rows):
        bg = (fills[i] if fills and i < len(fills) else None)
        cf = cell_fills[i] if cell_fills and i < len(cell_fills) else {}
        tds = []
        for j, v in enumerate(row):
            al = "left" if j == 0 else "center"
            c_bg = cf.get(j) or bg
            bgs = f"background:{c_bg};" if c_bg else ""
            tds.append(f'<td style="{cell}{bgs}text-align:{al};">{escape("" if v is None else str(v))}</td>')
        out.append("<tr>" + "".join(tds) + "</tr>")
    out.append("</table>")
    return "".join(out)


def cf_html(fragment):
    """Повний вміст формату буфера «HTML Format»: заголовок зі зміщеннями в БАЙТАХ (UTF-8) + HTML із маркерами фрагмента."""
    pre = "<html><body><!--StartFragment-->"
    post = "<!--EndFragment--></body></html>"
    header_tpl = "Version:0.9\r\nStartHTML:{:010d}\r\nEndHTML:{:010d}\r\nStartFragment:{:010d}\r\nEndFragment:{:010d}\r\n"
    hlen = len(header_tpl.format(0, 0, 0, 0).encode("utf-8"))
    b_pre, b_frag, b_post = pre.encode("utf-8"), fragment.encode("utf-8"), post.encode("utf-8")
    start_html = hlen
    start_frag = start_html + len(b_pre)
    end_frag = start_frag + len(b_frag)
    end_html = end_frag + len(b_post)
    return header_tpl.format(start_html, end_html, start_frag, end_frag).encode("utf-8") + b_pre + b_frag + b_post


def parse_cf_html(data):
    """Зворотний розбір (для перевірки): повертає (заголовок як словник, HTML-фрагмент)."""
    head, _, _ = data.partition(b"<html>")
    h = {}
    for line in head.decode("utf-8").split("\r\n"):
        if ":" in line:
            k, v = line.split(":", 1); h[k] = int(v) if v.strip().isdigit() else v
    return h, data[h["StartFragment"]:h["EndFragment"]].decode("utf-8")


def _set_windows_clipboard(text, html_bytes):
    import ctypes
    from ctypes import wintypes
    import time as _t
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL; kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = wintypes.LPVOID; kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]; kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    user32.OpenClipboard.argtypes = [wintypes.HWND]; user32.OpenClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]; user32.SetClipboardData.restype = wintypes.HANDLE
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]; user32.RegisterClipboardFormatW.restype = wintypes.UINT
    GMEM_MOVEABLE, CF_UNICODETEXT = 0x0002, 13
    fmt_html = user32.RegisterClipboardFormatW("HTML Format")

    def put(fmt, data):
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h: raise OSError("GlobalAlloc")
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, data, len(data)); kernel32.GlobalUnlock(h)
        if not user32.SetClipboardData(fmt, h): kernel32.GlobalFree(h); raise OSError("SetClipboardData")
    for _ in range(10):                                    # буфер може бути тимчасово зайнятий іншою програмою
        if user32.OpenClipboard(None): break
        _t.sleep(0.05)
    else:
        raise OSError("Буфер обміну зайнятий іншою програмою.")
    try:
        user32.EmptyClipboard()
        put(CF_UNICODETEXT, (text + "\0").encode("utf-16-le"))
        put(fmt_html, html_bytes + b"\0")
    finally:
        user32.CloseClipboard()


def copy_table(widget, headers, rows, fills=None, tsv=None, cell_fills=None):
    """Копіює таблицю: у Windows – текст + HTML із сіткою; в інших системах – лише текст.
    Повертає 'html' (сітку збережено) або 'text'."""
    text = tsv if tsv is not None else "\n".join("\t".join("" if v is None else str(v) for v in r) for r in [list(headers)] + [list(r) for r in rows])
    if sys.platform == "win32":
        try:
            _set_windows_clipboard(text, cf_html(build_html_table(headers, rows, fills, cell_fills=cell_fills)))
            return "html"
        except Exception:
            pass
    widget.clipboard_clear(); widget.clipboard_append(text)
    return "text"
