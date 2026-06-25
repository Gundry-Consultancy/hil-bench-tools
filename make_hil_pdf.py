#!/usr/bin/env python
"""
make_hil_pdf.py — render the soldering / attachment guide PDF from hil_map.json.

Reads the canonical map produced by build_map.py (no hardcoded table). Covers
the PR #933 drivers plus whatever is currently attached, grouped by mux channel,
with a dedicated soldering section. Run build_map.py first.

    python make_hil_pdf.py [-o out.pdf]
"""
import argparse
import json
from pathlib import Path
from fpdf import FPDF

HERE = Path(__file__).parent
MAP_PATH = HERE / "hil_map.json"

NAVY = (28, 42, 74)
GREY = (235, 237, 240)
SOLDER_BG = (255, 235, 205)
ATTACHED_BG = (224, 242, 224)
HEADER_BG = (28, 42, 74)
WHITE = (255, 255, 255)


def lat1(s):
    """Core PDF fonts are latin-1 only — fold common unicode to ASCII."""
    return (str(s).replace("—", "-").replace("–", "-").replace("→", "->")
            .replace("‘", "'").replace("’", "'")
            .replace("“", '"').replace("”", '"')
            .encode("latin-1", "replace").decode("latin-1"))


def load_map():
    if not MAP_PATH.exists():
        raise SystemExit(f"{MAP_PATH.name} not found — run `python build_map.py` first.")
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def status_label(r):
    if r.get("attached"):
        return "ATTACHED"
    if "real" in (r.get("note") or "").lower():
        return "NEED REAL PART"
    return "NEED"


def draw_table(pdf, headings, rows, col_w, fill_fn=None):
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(*HEADER_BG)
    pdf.set_text_color(*WHITE)
    for h, w in zip(headings, col_w):
        pdf.cell(w, 7, h, border=0, align="L", fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    for i, row in enumerate(rows):
        fill = False
        if fill_fn:
            c = fill_fn(row, i)
            if c:
                pdf.set_fill_color(*c)
                fill = True
        for val, w in zip(row, col_w):
            pdf.cell(w, 6.5, lat1(val), border="B", align="L", fill=fill)
        pdf.ln()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default=str(HERE / "hil_sensor_attachment_guide.pdf"))
    args = ap.parse_args()

    records = load_map()
    relevant = [r for r in records if r.get("pr933") or r.get("attached")]
    solder = [r for r in relevant if r.get("needs_solder")]

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 28, style="F")
    pdf.set_xy(12, 7)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, "HIL Sensor Attachment & Soldering Guide", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "QT Py ESP32-S3 N4R2  -  TCA9548A mux @ 0x77  -  generated from hil_map.json",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_text_color(0, 0, 0)

    # Section 1 — soldering
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, f"1.  Soldering / jumper adjustments  ({len(solder)} boards)",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 5, "These boards move off their default address to coexist. "
                               "All others sit at their factory/default address - no soldering.")
    pdf.ln(2)
    s_rows = [(r["name"], r["driver"] or "", r["channel_label"].split("(")[0].strip(),
               r["default_address"], r["address"], r["jumper_setting"]) for r in solder]
    draw_table(pdf, ("Sensor", "Driver", "Channel", "Default", "Target", "Jumper"),
               s_rows, (26, 30, 30, 18, 18, 48), fill_fn=lambda r, i: SOLDER_BG)
    pdf.ln(6)

    # Section 2 — full list grouped by channel
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, f"2.  Attachment list - PR #933 drivers + currently attached ({len(relevant)})",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 5, "Grouped by bus/mux channel. Green = already attached. "
                               "Amber = needs soldering. Find and attach the NEED rows.")
    pdf.ln(2)

    by_ch = {}
    for r in relevant:
        by_ch.setdefault(r["channel_index"], []).append(r)

    a_head = ("Sensor", "Driver", "Addr", "Jumper / note", "Status")
    a_cw = (26, 30, 16, 44, 54)

    def a_fill(row, i):
        # row carries the source record at index -1 (popped before render)
        rec = row[-1]
        if rec.get("needs_solder"):
            return SOLDER_BG
        if rec.get("attached"):
            return ATTACHED_BG
        return None

    for ch in sorted(by_ch):
        rows_src = sorted(by_ch[ch], key=lambda r: r["address"] or "")
        label = rows_src[0]["channel_label"]
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(*GREY)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 6.5, label, new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.set_text_color(0, 0, 0)
        rows = []
        for r in rows_src:
            jn = r["solder_action"] if r["needs_solder"] else (r.get("note") or "default/fixed")
            rows.append((r["name"], r["driver"] or "-", r["address"], jn[:46], status_label(r), r))
        # render with the record appended for fill, then trimmed per cell
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(*HEADER_BG); pdf.set_text_color(*WHITE)
        for h, w in zip(a_head, a_cw):
            pdf.cell(w, 7, h, fill=True)
        pdf.ln()
        pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "", 9)
        for row in rows:
            c = a_fill(row, 0)
            fill = bool(c)
            if c:
                pdf.set_fill_color(*c)
            for val, w in zip(row[:-1], a_cw):
                pdf.cell(w, 6.5, lat1(val), border="B", fill=fill)
            pdf.ln()
        pdf.ln(3)

    pdf.output(args.output)
    print("WROTE", args.output)


if __name__ == "__main__":
    main()
