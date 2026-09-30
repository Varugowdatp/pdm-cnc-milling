"""
Vector block diagrams for the reports.

Drawn with reportlab.graphics rather than embedded images so they stay
sharp at any zoom and print cleanly in black and white.
"""

from __future__ import annotations

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors

INK = colors.HexColor("#0f172a")
ACCENT = colors.HexColor("#0369a1")
ACCENT_BG = colors.HexColor("#e0f2fe")
OK = colors.HexColor("#15803d")
OK_BG = colors.HexColor("#dcfce7")
WARN_BG = colors.HexColor("#fef3c7")
WARN = colors.HexColor("#b45309")
GREY = colors.HexColor("#64748b")
GREY_BG = colors.HexColor("#f1f5f9")
RULE = colors.HexColor("#cbd5e1")


def _box(d, x, y, w, h, lines, fill=GREY_BG, stroke=GREY, fs=7.2, bold_first=True):
    d.add(Rect(x, y, w, h, fillColor=fill, strokeColor=stroke, strokeWidth=0.9))
    n = len(lines)
    total = n * (fs + 2.2)
    start = y + h / 2 + total / 2 - fs
    for i, text in enumerate(lines):
        font = "Helvetica-Bold" if (i == 0 and bold_first) else "Helvetica"
        d.add(String(x + w / 2, start - i * (fs + 2.2), text,
                     fontName=font, fontSize=fs if i == 0 else fs - 0.4,
                     fillColor=INK if i == 0 else GREY, textAnchor="middle"))


def _arrow(d, x1, y1, x2, y2, color=ACCENT, label=None):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1.1))
    # head
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    s = 4.2
    p = [x2, y2,
         x2 - s * math.cos(ang - 0.45), y2 - s * math.sin(ang - 0.45),
         x2 - s * math.cos(ang + 0.45), y2 - s * math.sin(ang + 0.45)]
    d.add(Polygon(p, fillColor=color, strokeColor=color))
    if label:
        d.add(String((x1 + x2) / 2, (y1 + y2) / 2 + 3, label,
                     fontName="Helvetica", fontSize=6, fillColor=GREY,
                     textAnchor="middle"))


# ==================================================================
def system_architecture(width=460):
    """End-to-end architecture: data in -> engine -> operator."""
    d = Drawing(width, 330)
    cw, ch = 96, 40
    col = [8, 128, 248, 360]

    d.add(String(width / 2, 316, "DATA ACQUISITION  (software replacement for the sensor rig)",
                 fontName="Helvetica-Bold", fontSize=7.6, fillColor=ACCENT, textAnchor="middle"))
    srcs = [("Manual Entry", "one reading"), ("CSV / Excel", "bulk upload"),
            ("Replay Simulator", "live feed"), ("REST client", "POST /api/predict")]
    for i, (a, b) in enumerate(srcs):
        _box(d, col[i], 262, cw, ch, [a, b], ACCENT_BG, ACCENT)

    for i in range(4):
        _arrow(d, col[i] + cw / 2, 262, col[i] + cw / 2 if i in (1, 2) else 232, 236)

    _box(d, 128, 200, 216, 34, ["FEATURE BUILDER", "shared with training - cannot drift"],
         GREY_BG, GREY)
    _arrow(d, 236, 200, 236, 176)

    # engine row
    _box(d, 8, 128, 104, 46, ["RANDOM FOREST", "300 trees", "horizon target"], OK_BG, OK)
    _box(d, 124, 128, 104, 46, ["PHYSICS ENGINE", "4 stress ratios", "first principles"], WARN_BG, WARN)
    _box(d, 240, 128, 104, 46, ["RULE CHECK", "hard thresholds", "deterministic"], WARN_BG, WARN)
    _box(d, 356, 128, 100, 46, ["EXPLAINER", "decision-path", "exact"], OK_BG, OK)

    for x in (60, 176, 292, 406):
        _arrow(d, 236, 176, x, 174)

    for x in (60, 176, 292, 406):
        _arrow(d, x, 128, 236, 106)

    _box(d, 92, 68, 288, 36,
         ["DECISION LAYER   health index | RUL | 4-band alarm",
          "worst-of-three wins  -  persistence filtered"], ACCENT_BG, ACCENT)
    _arrow(d, 236, 68, 236, 46)

    _box(d, 8, 8, 140, 36, ["SQLite STORE", "machines / readings / alarms"], GREY_BG, GREY)
    _box(d, 164, 8, 140, 36, ["REST API + SSE", "25 endpoints"], GREY_BG, GREY)
    _box(d, 320, 8, 136, 36, ["SCADA HMI", "6 operator screens"], OK_BG, OK)
    _arrow(d, 200, 46, 78, 44)
    _arrow(d, 236, 46, 234, 44)
    _arrow(d, 272, 46, 388, 44)
    return d


# ==================================================================
def hardware_mapping(width=460):
    """Synopsis block diagram mapped onto its software equivalent."""
    d = Drawing(width, 250)
    lw, rw, h = 186, 186, 26
    lx, rx = 6, 268

    d.add(String(lx + lw / 2, 236, "SYNOPSIS  (hardware)", fontName="Helvetica-Bold",
                 fontSize=8, fillColor=WARN, textAnchor="middle"))
    d.add(String(rx + rw / 2, 236, "THIS PROJECT  (software)", fontName="Helvetica-Bold",
                 fontSize=8, fillColor=OK, textAnchor="middle"))

    pairs = [
        ("Temperature / vibration / current sensors", "Sensor schema - same fields and units"),
        ("NodeMCU (ESP8266) acquisition", "Manual form + CSV upload + replay"),
        ("Wi-Fi upload to cloud", "HTTP POST to local REST API"),
        ("Cloud data store", "SQLite history and alarm log"),
        ("AI/ML model", "Random Forest (unchanged)"),
        ("RUL + fault alert output", "Health index, RUL, 4-band alarm"),
        ("Dashboard / mobile app", "SCADA HMI in the browser"),
    ]
    y = 200
    for a, b in pairs:
        _box(d, lx, y, lw, h, [a], WARN_BG, WARN, fs=6.6, bold_first=False)
        _box(d, rx, y, rw, h, [b], OK_BG, OK, fs=6.6, bold_first=False)
        _arrow(d, lx + lw + 3, y + h / 2, rx - 3, y + h / 2, GREY)
        y -= h + 3
    return d


# ==================================================================
def horizon_diagram(width=460):
    """Why the target had to change - reactive vs predictive labelling."""
    d = Drawing(width, 190)
    axis_y1, axis_y2 = 128, 44
    x0, x1 = 40, 430
    fail_x = 366

    for y, title, colr in ((axis_y1, "OLD TARGET  'failure_class'  -  the state RIGHT NOW", WARN),
                           (axis_y2, "NEW TARGET  'label_horizon'  -  the APPROACH", OK)):
        d.add(String(x0, y + 34, title, fontName="Helvetica-Bold", fontSize=7.4,
                     fillColor=colr))
        d.add(Line(x0, y, x1, y, strokeColor=GREY, strokeWidth=0.9))

    # normal spans
    d.add(Rect(x0, axis_y1 + 2, fail_x - x0, 16, fillColor=OK_BG, strokeColor=OK, strokeWidth=0.5))
    d.add(String((x0 + fail_x) / 2, axis_y1 + 7, "labelled Normal", fontName="Helvetica",
                 fontSize=6.4, fillColor=INK, textAnchor="middle"))
    d.add(Rect(fail_x, axis_y1 + 2, x1 - fail_x, 16, fillColor=colors.HexColor("#fee2e2"),
               strokeColor=colors.HexColor("#b91c1c"), strokeWidth=0.5))
    d.add(String((fail_x + x1) / 2, axis_y1 + 7, "FAILED", fontName="Helvetica-Bold",
                 fontSize=6.4, fillColor=colors.HexColor("#b91c1c"), textAnchor="middle"))

    horizon_x = fail_x - 78
    d.add(Rect(x0, axis_y2 + 2, horizon_x - x0, 16, fillColor=OK_BG, strokeColor=OK, strokeWidth=0.5))
    d.add(String((x0 + horizon_x) / 2, axis_y2 + 7, "labelled Normal", fontName="Helvetica",
                 fontSize=6.4, fillColor=INK, textAnchor="middle"))
    d.add(Rect(horizon_x, axis_y2 + 2, fail_x - horizon_x, 16, fillColor=WARN_BG,
               strokeColor=WARN, strokeWidth=0.5))
    d.add(String((horizon_x + fail_x) / 2, axis_y2 + 7, "labelled with the COMING failure",
                 fontName="Helvetica-Bold", fontSize=6, fillColor=WARN, textAnchor="middle"))
    d.add(Rect(fail_x, axis_y2 + 2, x1 - fail_x, 16, fillColor=colors.HexColor("#fee2e2"),
               strokeColor=colors.HexColor("#b91c1c"), strokeWidth=0.5))

    # failure marker
    for y in (axis_y1, axis_y2):
        d.add(Line(fail_x, y - 6, fail_x, y + 26, strokeColor=colors.HexColor("#b91c1c"),
                   strokeWidth=1.4))
    d.add(String(fail_x, 164, "FAILURE", fontName="Helvetica-Bold", fontSize=7,
                 fillColor=colors.HexColor("#b91c1c"), textAnchor="middle"))
    d.add(Line(fail_x, 160, fail_x, 150, strokeColor=colors.HexColor("#b91c1c"), strokeWidth=1))

    # alarm points
    d.add(String(x1 - 10, axis_y1 - 16, "alarm fires HERE  (-3.7 readings, too late)",
                 fontName="Helvetica-Oblique", fontSize=6.4, fillColor=WARN, textAnchor="end"))
    _arrow(d, fail_x + 24, axis_y1 - 12, fail_x + 24, axis_y1 - 2, WARN)

    d.add(String(x0 + 4, axis_y2 - 16, "alarm fires HERE  (+52 readings = 8.67 h of warning)",
                 fontName="Helvetica-Oblique", fontSize=6.4, fillColor=OK))
    _arrow(d, horizon_x - 40, axis_y2 - 12, horizon_x - 40, axis_y2 - 2, OK)

    d.add(String(x1, 12, "time  -->", fontName="Helvetica", fontSize=6.4,
                 fillColor=GREY, textAnchor="end"))
    return d
