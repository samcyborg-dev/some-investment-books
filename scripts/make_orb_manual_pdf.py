#!/usr/bin/env python3
"""Create a dependency-free PDF manual for the RangeLab ORB-30R strategy.

The repository does not require a PDF framework for this small document. This
renderer deliberately uses the PDF standard fonts so it works in the free
Chromebook/WebTerminal workflow without installing packages.
"""

from __future__ import annotations

import re
import textwrap
import unicodedata
from pathlib import Path

PAGE_W = 595.28
PAGE_H = 841.89
LEFT = 48.0
RIGHT = 48.0
TOP = 58.0
BOTTOM = 48.0
CONTENT_W = PAGE_W - LEFT - RIGHT

NAVY = (0.08, 0.14, 0.25)
TEAL = (0.06, 0.42, 0.42)
BLUE = (0.12, 0.31, 0.68)
SLATE = (0.22, 0.27, 0.34)
MUTED = (0.37, 0.42, 0.49)
LIGHT = (0.95, 0.97, 0.98)
PALE_TEAL = (0.90, 0.96, 0.95)
PALE_BLUE = (0.92, 0.95, 1.0)
BORDER = (0.78, 0.82, 0.86)
WHITE = (1.0, 1.0, 1.0)


def ascii_text(value: str) -> str:
    """Make text safe for the built-in PDF Type1 fonts."""
    value = value.replace("->", "to")
    value = value.replace("<-", "from")
    value = value.replace("×", "x").replace("≥", ">=").replace("≤", "<=")
    value = value.replace("—", "-").replace("–", "-").replace("’", "'")
    value = value.replace("•", "-").replace("✓", "OK")
    value = unicodedata.normalize("NFKD", value)
    return value.encode("ascii", "replace").decode("ascii")


def clean_inline(value: str) -> str:
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = value.replace("**", "").replace("__", "")
    value = value.replace("*", "")
    return ascii_text(value).strip()


def pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def color_cmd(color, fill=False) -> str:
    op = "rg" if fill else "RG"
    return f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} {op}"


def wrap_lines(value: str, font_size: float, width: float, mono=False) -> list[str]:
    value = clean_inline(value)
    if not value:
        return [""]
    char_width = font_size * (0.60 if mono else 0.49)
    count = max(12, int(width / char_width))
    return textwrap.wrap(
        value,
        width=count,
        break_long_words=True,
        break_on_hyphens=False,
        replace_whitespace=True,
    ) or [""]


class Page:
    def __init__(self, number: int):
        self.number = number
        self.commands: list[str] = []
        self.y = PAGE_H - TOP
        self._header()

    def _header(self):
        if self.number == 1:
            return
        self.text("RangeLab ORB-30R Advanced | User and walk-forward manual", LEFT, PAGE_H - 28, 8, "F1", MUTED)
        self.line(LEFT, PAGE_H - 37, PAGE_W - RIGHT, PAGE_H - 37, BORDER, 0.5)

    def footer(self):
        self.line(LEFT, 34, PAGE_W - RIGHT, 34, BORDER, 0.5)
        self.text("Research use only - not a broker execution record or profitability proof", LEFT, 21, 7.5, "F1", MUTED)
        label = f"Page {self.number}"
        self.text(label, PAGE_W - RIGHT - len(label) * 4.1, 21, 7.5, "F1", MUTED)

    def text(self, value: str, x: float, y: float, size: float, font="F1", color=SLATE):
        value = ascii_text(value)
        self.commands.append(
            f"BT /{font} {size:.2f} Tf {color_cmd(color, True)} 1 0 0 1 {x:.2f} {y:.2f} Tm ({pdf_escape(value)}) Tj ET"
        )

    def line(self, x1, y1, x2, y2, color=BORDER, width=0.7):
        self.commands.append(
            f"q {color_cmd(color)} {width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S Q"
        )

    def rect(self, x, y, w, h, fill=None, stroke=None, width=0.7):
        commands = ["q"]
        if fill:
            commands.append(color_cmd(fill, True))
        if stroke:
            commands.append(color_cmd(stroke))
            commands.append(f"{width:.2f} w")
        commands.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill and stroke:
            commands.append("B")
        elif fill:
            commands.append("f")
        else:
            commands.append("S")
        commands.append("Q")
        self.commands.append(" ".join(commands))


class ManualRenderer:
    def __init__(self):
        self.pages: list[Page] = []
        self.page = self.new_page()

    def new_page(self):
        page = Page(len(self.pages) + 1)
        self.pages.append(page)
        return page

    def ensure(self, height: float):
        if self.page.y - height < BOTTOM + 8:
            self.page.footer()
            self.page = self.new_page()

    def spacer(self, height=8):
        self.page.y -= height

    def paragraph(self, value: str, size=9.2, leading=13.2, color=SLATE, indent=0, mono=False):
        value = value.strip()
        if not value:
            self.spacer(5)
            return
        lines = wrap_lines(value, size, CONTENT_W - indent, mono=mono)
        self.ensure(len(lines) * leading + 4)
        for line in lines:
            self.page.text(line, LEFT + indent, self.page.y, size, "F3" if mono else "F1", color)
            self.page.y -= leading
        self.page.y -= 3

    def heading(self, value: str, level=2):
        size, leading, color, before = {
            1: (16.0, 20.0, NAVY, 14),
            2: (12.0, 15.0, TEAL, 10),
            3: (10.5, 13.5, BLUE, 7),
        }.get(level, (10.0, 13.0, NAVY, 6))
        self.ensure(before + leading + 8)
        self.page.y -= before
        self.page.text(clean_inline(value), LEFT, self.page.y, size, "F2", color)
        self.page.y -= leading
        if level == 1:
            self.page.line(LEFT, self.page.y + 3, PAGE_W - RIGHT, self.page.y + 3, TEAL, 1.1)
        self.page.y -= 4

    def rule(self):
        self.ensure(12)
        self.page.line(LEFT, self.page.y, PAGE_W - RIGHT, self.page.y, BORDER, 0.6)
        self.page.y -= 10

    def callout(self, value: str, fill=PALE_TEAL, stroke=TEAL):
        lines = wrap_lines(value, 9.2, CONTENT_W - 24)
        height = len(lines) * 13.2 + 18
        self.ensure(height + 8)
        bottom = self.page.y - height + 4
        self.page.rect(LEFT, bottom, CONTENT_W, height, fill=fill, stroke=stroke, width=0.8)
        y = self.page.y - 8
        for line in lines:
            self.page.text(line, LEFT + 11, y, 9.2, "F1", NAVY)
            y -= 13.2
        self.page.y = bottom - 9

    def bullet(self, value: str, number=None):
        prefix = f"{number}." if number is not None else "-"
        prefix_w = 19
        lines = wrap_lines(value, 9.1, CONTENT_W - prefix_w - 5)
        self.ensure(len(lines) * 12.7 + 3)
        self.page.text(prefix, LEFT, self.page.y, 9.1, "F2", TEAL)
        self.page.text(lines[0], LEFT + prefix_w, self.page.y, 9.1, "F1", SLATE)
        self.page.y -= 12.7
        for line in lines[1:]:
            self.page.text(line, LEFT + prefix_w, self.page.y, 9.1, "F1", SLATE)
            self.page.y -= 12.7
        self.page.y -= 2

    def table(self, rows: list[list[str]]):
        if not rows:
            return
        cols = max(len(row) for row in rows)
        if cols != 2:
            for row in rows:
                self.paragraph(" | ".join(row), size=8.4, leading=11.5, indent=4)
            return
        left_w = 156.0
        right_w = CONTENT_W - left_w
        x_left = LEFT
        x_right = LEFT + left_w
        for index, row in enumerate(rows):
            left = clean_inline(row[0] if len(row) > 0 else "")
            right = clean_inline(row[1] if len(row) > 1 else "")
            left_lines = wrap_lines(left, 8.1, left_w - 12)
            right_lines = wrap_lines(right, 8.1, right_w - 12)
            row_lines = max(len(left_lines), len(right_lines))
            row_h = row_lines * 10.8 + 10
            if index == 0:
                left_lines = wrap_lines(left, 8.0, left_w - 12)
                right_lines = wrap_lines(right, 8.0, right_w - 12)
                row_lines = max(len(left_lines), len(right_lines))
                row_h = row_lines * 10.8 + 10
            self.ensure(row_h + 2)
            bottom = self.page.y - row_h + 3
            fill = NAVY if index == 0 else (WHITE if index % 2 else LIGHT)
            self.page.rect(LEFT, bottom, CONTENT_W, row_h, fill=fill, stroke=BORDER, width=0.45)
            self.page.line(x_right, bottom, x_right, bottom + row_h, BORDER, 0.45)
            font = "F2" if index == 0 else "F1"
            color = WHITE if index == 0 else SLATE
            y_left = self.page.y - 9
            y_right = self.page.y - 9
            for line in left_lines:
                self.page.text(line, x_left + 6, y_left, 8.0 if index == 0 else 8.1, font, color)
                y_left -= 10.8
            for line in right_lines:
                self.page.text(line, x_right + 6, y_right, 8.0 if index == 0 else 8.1, font, color)
                y_right -= 10.8
            self.page.y = bottom - 1
        self.page.y -= 7

    def cover(self):
        self.page.y = PAGE_H - 110
        self.page.text("RANGELAB", LEFT, self.page.y, 11, "F2", TEAL)
        self.page.y -= 31
        self.page.text("ORB-30R Advanced", LEFT, self.page.y, 27, "F2", NAVY)
        self.page.y -= 31
        self.page.text("User, testing, and walk-forward manual", LEFT, self.page.y, 13, "F1", BLUE)
        self.page.y -= 22
        self.page.line(LEFT, self.page.y, PAGE_W - RIGHT, self.page.y, TEAL, 2.0)
        self.page.y -= 28
        self.paragraph("A practical operating guide for the free-plan-compatible TradingView research strategy, including setup, cost controls, weekly logging, and a disciplined walk-forward process.", size=11, leading=16, color=SLATE)
        self.spacer(14)
        self.callout("READ THIS FIRST: The script is for research, backtesting, paper testing, and alert observation. It does not place broker orders. A TradingView strategy fill is a modeled fill, not an execution confirmation. One week of results cannot establish a durable edge.", fill=PALE_BLUE, stroke=BLUE)
        self.spacer(16)
        self.heading("Document control", 2)
        self.table([
            ["Item", "Value"],
            ["Document date", "12 September 2026"],
            ["Source script", "pinescript/RangeLab_ORB30R_Advanced.pine"],
            ["Baseline chart", "Five-minute standard candlesticks"],
            ["Baseline state", "Bar Magnifier disabled for free-plan compatibility"],
            ["Instruments", "ES and MES, analyzed independently"],
        ])
        self.spacer(5)
        self.heading("Immediate plan", 2)
        for item in [
            "Archive this week's Strategy Tester report and List of Trades as Baseline v1 - Week 1.",
            "Do not change parameters because of this week's P&L.",
            "Run the same settings unchanged next week and record every session, including no-trade days.",
            "After enough history, use the rolling walk-forward design in Section 8.",
        ]:
            self.bullet(item)
        self.page.y = min(self.page.y, 115)
        self.callout("The correct Pine source begins with //@version=6. Do not paste the MT5 file RangeLab_HistoryExporter.mq5 into Pine Editor.", fill=PALE_TEAL, stroke=TEAL)

    def render_markdown(self, path: Path):
        lines = path.read_text(encoding="utf-8").splitlines()
        i = 0
        while i < len(lines):
            raw = lines[i].rstrip()
            stripped = raw.strip()
            if not stripped:
                self.spacer(4)
                i += 1
                continue
            if stripped == "---":
                self.rule()
                i += 1
                continue
            if stripped.startswith("# "):
                # The cover already contains the title and document control.
                i += 1
                continue
            if stripped.startswith("## "):
                self.heading(stripped[3:], 1)
                i += 1
                continue
            if stripped.startswith("### "):
                self.heading(stripped[4:], 2)
                i += 1
                continue
            if stripped.startswith(">"):
                collected = [stripped.lstrip("> ")]
                i += 1
                while i < len(lines) and lines[i].strip().startswith(">"):
                    collected.append(lines[i].strip().lstrip("> "))
                    i += 1
                self.callout(" ".join(collected), fill=PALE_TEAL, stroke=TEAL)
                continue
            if stripped.startswith("|"):
                rows = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    row = lines[i].strip().strip("|")
                    cells = [cell.strip() for cell in row.split("|")]
                    if not all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                        rows.append(cells)
                    i += 1
                self.table(rows)
                continue
            match = re.match(r"^(\d+)\.\s+(.*)$", stripped)
            if match:
                self.bullet(match.group(2), number=match.group(1))
                i += 1
                continue
            if stripped.startswith("- "):
                self.bullet(stripped[2:])
                i += 1
                continue
            self.paragraph(stripped)
            i += 1

    def finish(self):
        self.page.footer()
        return self.pages


def build_pdf(output: Path, source: Path):
    renderer = ManualRenderer()
    renderer.cover()
    renderer.render_markdown(source)
    pages = renderer.finish()

    objects: list[bytes] = []

    def add(obj: str | bytes) -> int:
        data = obj.encode("latin-1") if isinstance(obj, str) else obj
        objects.append(data)
        return len(objects)

    catalog_id = add("")
    pages_id = add("")
    font_regular = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font_bold = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    font_mono = add("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    page_ids = []
    for page in pages:
        stream = "\n".join(page.commands).encode("latin-1")
        content_id = add(f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream")
        page_id = add(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_W:.2f} {PAGE_H:.2f}] "
            f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R /F3 {font_mono} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("latin-1")
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R /PageMode /UseNone >>".encode("latin-1")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        handle.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for object_number, data in enumerate(objects, start=1):
            offsets.append(handle.tell())
            handle.write(f"{object_number} 0 obj\n".encode("ascii"))
            handle.write(data)
            handle.write(b"\nendobj\n")
        xref_offset = handle.tell()
        handle.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        handle.write(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            handle.write(f"{offset:010d} 00000 n \n".encode("ascii"))
        handle.write(
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R "
            f"/Info << /Title (RangeLab ORB-30R Advanced Manual) /Author (RangeLab research) >> >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n".encode("latin-1")
        )

    print(f"Wrote {output} ({len(pages)} pages, {output.stat().st_size} bytes)")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    build_pdf(root / "pinescript" / "RangeLab_ORB30R_Manual.pdf", root / "pinescript" / "RangeLab_ORB30R_Manual.md")
