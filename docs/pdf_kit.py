"""
============================================================
 PDF TOOLKIT  -  shared building blocks for the three reports
============================================================
A thin, opinionated layer over ReportLab's platypus so the three
documents in docs/ share one visual identity and one set of helpers.

Design notes
------------
* A4 with generous margins - these are documents meant to be printed
  and read, not dashboards.
* The palette is the project's own (src/config.py THEME), desaturated
  for paper. Screens are dark; print is not, so the dark theme is used
  only for code blocks and accent rules.
* Screenshots are auto-trimmed of dead background before placement -
  a full-page capture of a short screen is mostly empty pixels, and
  scaling that to page width wastes half a page.
"""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "docs" / "screenshots"

# ------------------------------------------------------------------
#  PALETTE  (print-adapted from the project theme)
# ------------------------------------------------------------------
INK        = colors.HexColor("#0f172a")
BODY       = colors.HexColor("#1e293b")
MUTED      = colors.HexColor("#64748b")
RULE       = colors.HexColor("#cbd5e1")
ACCENT     = colors.HexColor("#0369a1")
ACCENT_BG  = colors.HexColor("#e0f2fe")
OK         = colors.HexColor("#15803d")
OK_BG      = colors.HexColor("#dcfce7")
WARN       = colors.HexColor("#b45309")
WARN_BG    = colors.HexColor("#fef3c7")
CRIT       = colors.HexColor("#b91c1c")
CRIT_BG    = colors.HexColor("#fee2e2")
CODE_BG    = colors.HexColor("#0f172a")
TABLE_HEAD = colors.HexColor("#1e293b")
ZEBRA      = colors.HexColor("#f8fafc")

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


# ------------------------------------------------------------------
#  STYLES
# ------------------------------------------------------------------
def build_styles():
    ss = getSampleStyleSheet()
    S = {}

    S["title"] = ParagraphStyle("title", parent=ss["Title"], fontName="Helvetica-Bold",
                                fontSize=26, leading=31, textColor=INK, spaceAfter=6)
    S["subtitle"] = ParagraphStyle("subtitle", parent=ss["Normal"], fontName="Helvetica",
                                   fontSize=13, leading=18, textColor=MUTED,
                                   alignment=TA_CENTER, spaceAfter=4)
    S["cover_meta"] = ParagraphStyle("cover_meta", parent=ss["Normal"], fontName="Helvetica",
                                     fontSize=10.5, leading=17, textColor=BODY,
                                     alignment=TA_CENTER)

    S["h1"] = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold",
                             fontSize=17, leading=21, textColor=INK,
                             spaceBefore=16, spaceAfter=9)
    S["h2"] = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                             fontSize=13, leading=17, textColor=ACCENT,
                             spaceBefore=13, spaceAfter=6)
    S["h3"] = ParagraphStyle("h3", parent=ss["Heading3"], fontName="Helvetica-Bold",
                             fontSize=11, leading=15, textColor=INK,
                             spaceBefore=10, spaceAfter=4)

    S["body"] = ParagraphStyle("body", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=9.8, leading=14.6, textColor=BODY,
                               alignment=TA_JUSTIFY, spaceAfter=7)
    S["body_left"] = ParagraphStyle("body_left", parent=S["body"], alignment=TA_LEFT)
    S["small"] = ParagraphStyle("small", parent=S["body"], fontSize=8.6, leading=12.4,
                                textColor=MUTED)
    S["caption"] = ParagraphStyle("caption", parent=ss["Normal"], fontName="Helvetica-Oblique",
                                  fontSize=8.6, leading=12, textColor=MUTED,
                                  alignment=TA_CENTER, spaceBefore=4, spaceAfter=12)
    S["bullet"] = ParagraphStyle("bullet", parent=S["body"], leftIndent=13,
                                 bulletIndent=3, spaceAfter=4, alignment=TA_LEFT)
    S["code"] = ParagraphStyle("code", parent=ss["Code"], fontName="Courier",
                               fontSize=8.2, leading=11.4,
                               textColor=colors.HexColor("#e2e8f0"),
                               backColor=CODE_BG, borderPadding=7,
                               leftIndent=2, rightIndent=2, spaceAfter=9)
    S["cell"] = ParagraphStyle("cell", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=8.4, leading=11.6, textColor=BODY)
    S["cell_b"] = ParagraphStyle("cell_b", parent=S["cell"], fontName="Helvetica-Bold")
    S["cell_mono"] = ParagraphStyle("cell_mono", parent=S["cell"], fontName="Courier",
                                    fontSize=7.9, leading=11)
    S["cell_head"] = ParagraphStyle("cell_head", parent=S["cell"], fontName="Helvetica-Bold",
                                    fontSize=8.2, textColor=colors.white)
    S["toc1"] = ParagraphStyle("toc1", parent=S["body"], fontName="Helvetica-Bold",
                               fontSize=10, leading=16, spaceAfter=1, alignment=TA_LEFT)
    S["toc2"] = ParagraphStyle("toc2", parent=S["body"], fontSize=9.4, leading=14,
                               leftIndent=14, spaceAfter=0, alignment=TA_LEFT)
    return S


STYLES = build_styles()


# ------------------------------------------------------------------
#  DOCUMENT
# ------------------------------------------------------------------
class Report(BaseDocTemplate):
    """A4 document with a running footer and page numbers (cover exempt)."""

    def __init__(self, path, title, footer_text, **kw):
        super().__init__(str(path), pagesize=A4,
                         leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=MARGIN, bottomMargin=18 * mm,
                         title=title, author="GEC K R Pete - ECE", **kw)
        self.footer_text = footer_text

        frame = Frame(MARGIN, 18 * mm, CONTENT_W,
                      PAGE_H - MARGIN - 18 * mm, id="body")
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[frame], onPage=self._cover_page),
            PageTemplate(id="main", frames=[frame], onPage=self._main_page),
        ])

    def _cover_page(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(ACCENT)
        canvas.rect(0, PAGE_H - 12, PAGE_W, 12, stroke=0, fill=1)
        canvas.setFillColor(INK)
        canvas.rect(0, 0, PAGE_W, 8, stroke=0, fill=1)
        canvas.restoreState()

    def _main_page(self, canvas, doc):
        canvas.saveState()
        # header rule
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN, PAGE_H - MARGIN + 6, PAGE_W - MARGIN, PAGE_H - MARGIN + 6)
        canvas.setFont("Helvetica", 7.4)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, PAGE_H - MARGIN + 10, self.footer_text)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 10,
                               "AI-Based Predictive Maintenance")
        # footer
        canvas.line(MARGIN, 15 * mm, PAGE_W - MARGIN, 15 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(PAGE_W / 2, 10 * mm, str(canvas.getPageNumber()))
        canvas.restoreState()


# ------------------------------------------------------------------
#  CONTENT HELPERS
# ------------------------------------------------------------------
def esc(t) -> str:
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# Inline tags ReportLab understands and that the reports use deliberately.
_ALLOWED_TAG = re.compile(
    r"</?(?:b|i|u|br|sub|super|font(?:\s[^<>]*)?)\s*/?>", re.IGNORECASE)


def smart_esc(t) -> str:
    """
    Escape text for a Paragraph while preserving intentional inline markup.

    Table cells are authored with <b> and <i> in them, so escaping
    everything renders the tags literally on the page - which is exactly
    what happened in the first draft of the interface guide. Escaping
    nothing is worse: a stray '<' or '&' in real data aborts the build.

    So: protect the known-good tags, escape everything else, restore.
    """
    s = str(t)
    keep = []

    def stash(m):
        keep.append(m.group(0))
        return f"\x00{len(keep) - 1}\x00"

    s = _ALLOWED_TAG.sub(stash, s)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for i, tag in enumerate(keep):
        s = s.replace(f"\x00{i}\x00", tag)
    return s


def P(text, style="body"):
    return Paragraph(text, STYLES[style])


def H1(text):
    return Paragraph(esc(text), STYLES["h1"])


def H2(text):
    return Paragraph(esc(text), STYLES["h2"])


def H3(text):
    return Paragraph(esc(text), STYLES["h3"])


def bullets(items, style="bullet"):
    return [Paragraph(t, STYLES[style], bulletText="•") for t in items]


def code(text):
    body = esc(text).replace("\n", "<br/>").replace(" ", "&nbsp;")
    return Paragraph(f'<font face="Courier">{body}</font>', STYLES["code"])


def spacer(h=6):
    return Spacer(1, h)


def rule(color=RULE, width=0.8):
    t = Table([[""]], colWidths=[CONTENT_W], rowHeights=[1])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), width, color)]))
    return t


def table(rows, widths=None, head=True, zebra=True, align=None,
          font_size=8.4, head_bg=TABLE_HEAD):
    """
    rows[0] is the header when head=True. Cells may be strings or
    already-built flowables.
    """
    data = []
    for r_i, row in enumerate(rows):
        out = []
        for c_i, cell in enumerate(row):
            if hasattr(cell, "wrap"):
                out.append(cell)
            else:
                st = "cell_head" if (head and r_i == 0) else "cell"
                out.append(Paragraph(smart_esc(cell), STYLES[st]))
        data.append(out)

    t = Table(data, colWidths=widths, repeatRows=1 if head else 0, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if head:
        style += [("BACKGROUND", (0, 0), (-1, 0), head_bg)]
    if zebra:
        start = 1 if head else 0
        for i in range(start, len(data)):
            if (i - start) % 2 == 1:
                style.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    if align:
        for col, a in align.items():
            style.append(("ALIGN", (col, 0), (col, -1), a))
    t.setStyle(TableStyle(style))
    return t


def callout(title, body, kind="info"):
    """A tinted box for the things a reader must not miss."""
    palette = {
        "info": (ACCENT, ACCENT_BG),
        "ok":   (OK, OK_BG),
        "warn": (WARN, WARN_BG),
        "crit": (CRIT, CRIT_BG),
    }
    fg, bg = palette.get(kind, palette["info"])

    inner = [Paragraph(f'<font color="{fg.hexval()}"><b>{title}</b></font>',
                       STYLES["body_left"])]
    if body:
        inner.append(Paragraph(body, STYLES["body_left"]))

    t = Table([[inner]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, fg),
        ("BOX", (0, 0), (-1, -1), 0.4, fg),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def kpi_row(items, cols=None):
    """items: [(label, value, note)] rendered as a strip of stat cells."""
    cols = cols or len(items)
    cells = []
    for label, value, note in items:
        cells.append([
            Paragraph(f'<font size="7.2" color="{MUTED.hexval()}">{esc(label).upper()}</font>',
                      STYLES["cell"]),
            Paragraph(f'<font size="15" color="{INK.hexval()}"><b>{esc(value)}</b></font>',
                      STYLES["cell"]),
            Paragraph(f'<font size="7" color="{MUTED.hexval()}">{esc(note)}</font>',
                      STYLES["cell"]),
        ])
    w = CONTENT_W / cols
    t = Table([cells], colWidths=[w] * cols)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, RULE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, RULE),
        ("BACKGROUND", (0, 0), (-1, -1), ZEBRA),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


# ------------------------------------------------------------------
#  IMAGES
# ------------------------------------------------------------------
def _trim(path: Path, out_dir: Path) -> Path:
    """
    Trim uniform background from the bottom/right of a full-page capture.

    A full_page screenshot of a short screen is mostly empty pixels;
    scaling that to page width wastes most of the figure's height budget.
    """
    from PIL import Image as PILImage, ImageChops

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / (path.stem + "_trim.png")
    if dest.exists() and dest.stat().st_mtime > path.stat().st_mtime:
        return dest

    im = PILImage.open(path).convert("RGB")
    # background is the page colour, sampled from a known-empty corner
    bg_pixel = im.getpixel((im.width - 6, im.height - 6))
    bg = PILImage.new("RGB", im.size, bg_pixel)
    diff = ImageChops.difference(im, bg)
    box = diff.getbbox()

    if box:
        left, top, right, bottom = box
        pad = 8
        box = (max(0, left - pad), max(0, top - pad),
               min(im.width, right + pad), min(im.height, bottom + pad))
        im = im.crop(box)

    im.save(dest, optimize=True)
    return dest


def figure(name, caption, width_frac=1.0, max_h=None, trim=True, crop=None):
    """
    Place a screenshot scaled to the text width.

    `crop` is an optional (l, t, r, b) fraction tuple for zooming into
    one region of a screen - used by the UI guide to show a single panel
    at a legible size instead of a whole page shrunk to nothing.
    """
    src = SHOTS / f"{name}.png"
    if not src.exists():
        return [P(f'<i>[missing figure: {name}.png]</i>', "small")]

    work = src
    if crop:
        from PIL import Image as PILImage
        out_dir = ROOT / "docs" / "_prepared"
        out_dir.mkdir(parents=True, exist_ok=True)
        tag = "-".join(str(round(c, 3)) for c in crop)
        dest = out_dir / f"{src.stem}_crop_{tag}.png"
        if not dest.exists():
            im = PILImage.open(src).convert("RGB")
            l, t, r, b = crop
            im.crop((int(l * im.width), int(t * im.height),
                     int(r * im.width), int(b * im.height))).save(dest, optimize=True)
        work = dest
    elif trim:
        work = _trim(src, ROOT / "docs" / "_prepared")

    from PIL import Image as PILImage
    with PILImage.open(work) as im:
        iw, ih = im.size

    w = CONTENT_W * width_frac
    h = w * ih / iw
    if max_h and h > max_h:
        h = max_h
        w = h * iw / ih

    img = Image(str(work), width=w, height=h)
    img.hAlign = "CENTER"

    block = [img, Paragraph(caption, STYLES["caption"])]
    return [KeepTogether(block)] if h < 480 else block


# ------------------------------------------------------------------
#  COVER
# ------------------------------------------------------------------
def cover(title, subtitle, doc_kind, meta_lines, tagline=None):
    story = [Spacer(1, 44)]

    story.append(Paragraph(
        f'<font size="9" color="{ACCENT.hexval()}"><b>{esc(doc_kind).upper()}</b></font>',
        STYLES["subtitle"]))
    story.append(Spacer(1, 14))
    story.append(Paragraph(esc(title), STYLES["title"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(esc(subtitle), STYLES["subtitle"]))
    story.append(Spacer(1, 20))

    t = Table([[""]], colWidths=[70])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 2.4, ACCENT)]))
    t.hAlign = "CENTER"
    story.append(t)
    story.append(Spacer(1, 26))

    if tagline:
        story.append(callout("", tagline, "ok"))
        story.append(Spacer(1, 24))

    rows = [[Paragraph(f"<b>{esc(k)}</b>", STYLES["cell"]),
             Paragraph(esc(v), STYLES["cell"])] for k, v in meta_lines]
    mt = Table(rows, colWidths=[120, CONTENT_W - 200])
    mt.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    mt.hAlign = "CENTER"
    story.append(mt)

    story.append(Spacer(1, 40))
    story.append(Paragraph(
        "Government Engineering College, K. R. Pete<br/>"
        "Department of Electronics &amp; Communication Engineering",
        STYLES["cover_meta"]))

    story.append(NextPageTemplate("main"))
    story.append(PageBreak())
    return story


def toc(entries):
    """entries: [(level, text)] - a plain, hand-built contents list."""
    out = [H1("Contents"), spacer(4)]
    for level, text in entries:
        out.append(Paragraph(esc(text), STYLES["toc1" if level == 1 else "toc2"]))
    out.append(PageBreak())
    return out
