"""
Builds a Flight E-Ticket Receipt PDF matching the agency's style spec:
light blue-gray page background, white rounded cards with soft shadows,
navy/blue accent palette, a pill status badge, a dark navy info bar,
tight label->value and airport->name clusters with one deliberate large
gap before the big time display, and rounded baggage panels.

Font: Lato (embedded). The spec names "Inter / Helvetica Neue / Segoe UI
style" as examples of the desired look (clean geometric sans, bold
headings). Inter itself is only distributable as a variable font, which
ReportLab cannot split into separate static Bold/Black weights, so Lato is
used instead — it satisfies the same brief (bold headings, regular body).
"""
import os
import re
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
    TableStyle, KeepTogether, Flowable,
)
from reportlab.pdfgen import canvas as canvas_module

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
pdfmetrics.registerFont(TTFont("Lato", os.path.join(FONTS_DIR, "Lato-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Lato-Bold", os.path.join(FONTS_DIR, "Lato-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Lato-Italic", os.path.join(FONTS_DIR, "Lato-Italic.ttf")))
pdfmetrics.registerFont(TTFont("Lato-Black", os.path.join(FONTS_DIR, "Lato-Black.ttf")))

# ---------------------------------------------------------------------------
# Palette — exact hex values from the style spec
# ---------------------------------------------------------------------------
PAGE_BG = colors.HexColor("#F4F6F9")
CARD_WHITE = colors.HexColor("#FFFFFF")
NAVY = colors.HexColor("#1A365D")
MUTED = colors.HexColor("#718096")          # labels
BODY_GRAY = colors.HexColor("#4A5568")      # darker body gray
ACCENT_BLUE = colors.HexColor("#2B6CB0")
BORDER = colors.HexColor("#E2E8F0")
PANEL_LIGHT = colors.HexColor("#F7FAFC")
STATUS_BG = colors.HexColor("#C6F6D5")
STATUS_TEXT = colors.HexColor("#38A169")
SHADOW = colors.Color(0, 0, 0, alpha=0.10)

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 16 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

styles = getSampleStyleSheet()


def _tracked(text: str, spacer="\u00A0") -> str:
    """Fake letter-spacing for short uppercase headers (ReportLab core
    Paragraph has no letter-spacing property).

    Important: ReportLab collapses any run of regular ' ' characters down
    to a single space no matter how many there are, so naively preserving
    the source text's spaces produces IDENTICAL gaps at word boundaries
    and between tracked letters (that was the bug — words looked like they
    had no space at all). Non-breaking spaces (\u00A0) are not collapsed,
    so real word-boundaries get 3 of them (clearly wider) while individual
    letters get 1 (tight tracking)."""
    out = []
    for ch in text:
        if ch == " ":
            out.append(spacer * 3)
        else:
            out.append(ch)
            out.append(spacer)
    return "".join(out)


# ---------------------------------------------------------------------------
# Paragraph styles
# ---------------------------------------------------------------------------
STYLE_LOGO = ParagraphStyle("Logo", parent=styles["Normal"], fontName="Lato-Black", fontSize=13, textColor=NAVY, leading=15)
STYLE_TAGLINE = ParagraphStyle("Tagline", parent=styles["Normal"], fontName="Lato-Bold", fontSize=6, textColor=MUTED, leading=8)
STYLE_RECEIPT_LABEL = ParagraphStyle("ReceiptLabel", parent=styles["Normal"], fontName="Lato-Black", fontSize=9, textColor=ACCENT_BLUE, alignment=2, leading=11)

STYLE_BAR_LABEL = ParagraphStyle("BarLabel", parent=styles["Normal"], fontName="Lato-Bold", fontSize=6, textColor=colors.HexColor("#B9C7DA"), leading=8)
STYLE_BAR_VALUE = ParagraphStyle("BarValue", parent=styles["Normal"], fontName="Lato-Bold", fontSize=7.5, textColor=colors.white, leading=9)

STYLE_SECTION_TITLE = ParagraphStyle("SectionTitle", parent=styles["Normal"], fontName="Lato-Black", fontSize=7.5, textColor=NAVY, leading=9)

STYLE_TABLE_HEADER = ParagraphStyle("TableHeader", parent=styles["Normal"], fontName="Lato-Bold", fontSize=6, textColor=MUTED, leading=8)
STYLE_TABLE_VALUE = ParagraphStyle("TableValue", parent=styles["Normal"], fontName="Lato-Bold", fontSize=6.5, textColor=NAVY, leading=8.5)
STYLE_TABLE_VALUE_REG = ParagraphStyle("TableValueReg", parent=styles["Normal"], fontName="Lato", fontSize=6.5, textColor=BODY_GRAY, leading=8)

STYLE_AIRPORT_CODE = ParagraphStyle("AirportCode", parent=styles["Normal"], fontName="Lato-Black", fontSize=9, textColor=ACCENT_BLUE, leading=10.5)
STYLE_AIRPORT_NAME = ParagraphStyle("AirportName", parent=styles["Normal"], fontName="Lato", fontSize=6, textColor=MUTED, leading=7.5)
STYLE_BIG_TIME = ParagraphStyle("BigTime", parent=styles["Normal"], fontName="Lato-Black", fontSize=14, textColor=NAVY, leading=16)
STYLE_FLIGHT_DATE = ParagraphStyle("FlightDate", parent=styles["Normal"], fontName="Lato", fontSize=6.5, textColor=MUTED, leading=8)
STYLE_NONSTOP = ParagraphStyle("NonStop", parent=styles["Normal"], fontName="Lato-Bold", fontSize=6, textColor=MUTED, leading=7, alignment=1)
STYLE_DURATION = ParagraphStyle("Duration", parent=styles["Normal"], fontName="Lato", fontSize=6, textColor=MUTED, alignment=1, leading=7)
STYLE_SEGMENT_META = ParagraphStyle("SegmentMeta", parent=styles["Normal"], fontName="Lato", fontSize=6, textColor=BODY_GRAY, leading=8)
STYLE_SEGMENT_LABEL = ParagraphStyle("SegmentLabel", parent=styles["Normal"], fontName="Lato-Bold", fontSize=6, textColor=ACCENT_BLUE, leading=7.5)

STYLE_BAG_LABEL = ParagraphStyle("BagLabel", parent=styles["Normal"], fontName="Lato-Bold", fontSize=6, textColor=MUTED, alignment=1, leading=7.5)
STYLE_BAG_NUMBER = ParagraphStyle("BagNumber", parent=styles["Normal"], fontName="Lato-Black", fontSize=10.5, textColor=ACCENT_BLUE, alignment=1, leading=12)
STYLE_BAG_DESC = ParagraphStyle("BagDesc", parent=styles["Normal"], fontName="Lato", fontSize=6, textColor=MUTED, alignment=1, leading=7.5)

STYLE_FOOTER_HEADING = ParagraphStyle("FooterHeading", parent=styles["Normal"], fontName="Lato-Bold", fontSize=8.5, textColor=NAVY, leading=11)
STYLE_FOOTER_BODY = ParagraphStyle("FooterBody", parent=styles["Normal"], fontName="Lato", fontSize=7.5, textColor=MUTED, leading=10.5)
STYLE_FOOTER_THANKS = ParagraphStyle("FooterThanks", parent=styles["Normal"], fontName="Lato-Bold", fontSize=8.5, textColor=NAVY, alignment=1, leading=11)


def _p(text, style):
    return Paragraph(text if text not in (None, "") else "None", style)


# ---------------------------------------------------------------------------
# Custom flowables: rounded card w/ shadow, pill badge, dashed connector
# ---------------------------------------------------------------------------
class RoundedCard(Flowable):
    """Wraps a content flowable in a white (or custom) rounded rect with a
    soft drop shadow — no hard borders, per spec."""

    def __init__(self, content, width, pad=14, radius=9, bg=CARD_WHITE, shadow=True, border=None):
        super().__init__()
        self.content = content
        self.width = width
        self.pad = pad
        self.radius = radius
        self.bg = bg
        self.shadow = shadow
        self.border = border
        self.height = 0

    def wrap(self, availWidth, availHeight):
        w, h = self.content.wrap(self.width - 2 * self.pad, availHeight - 2 * self.pad)
        self.height = h + 2 * self.pad
        return self.width, self.height

    def draw(self):
        c = self.canv
        if self.shadow:
            c.saveState()
            c.setFillColor(SHADOW)
            c.roundRect(1.2, -1.8, self.width, self.height, self.radius, fill=1, stroke=0)
            c.restoreState()
        c.saveState()
        c.setFillColor(self.bg)
        if self.border:
            c.setStrokeColor(self.border)
            c.setLineWidth(0.75)
            c.roundRect(0, 0, self.width, self.height, self.radius, fill=1, stroke=1)
        else:
            c.roundRect(0, 0, self.width, self.height, self.radius, fill=1, stroke=0)
        c.restoreState()
        self.content.drawOn(self.canv, self.pad, self.pad)


class StatusPill(Flowable):
    """Small rounded pill badge, e.g. green 'CONFIRMED'."""

    def __init__(self, text, bg, text_color, font="Lato-Bold", font_size=7.5, pad_x=11, pad_y=4.5):
        super().__init__()
        self.text = text
        self.bg = bg
        self.text_color = text_color
        self.font = font
        self.font_size = font_size
        self.pad_x = pad_x
        self.pad_y = pad_y
        self.width = pdfmetrics.stringWidth(text, font, font_size) + 2 * pad_x
        self.height = font_size + 2 * pad_y

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(self.bg)
        c.roundRect(0, 0, self.width, self.height, self.height / 2, fill=1, stroke=0)
        c.setFillColor(self.text_color)
        c.setFont(self.font, self.font_size)
        c.drawCentredString(self.width / 2, self.pad_y - 0.5, self.text)
        c.restoreState()


class PlaneBadge(Flowable):
    """Small circular icon with a simple plane silhouette, used next to
    the agency name in the header."""

    def __init__(self, diameter=16, bg=ACCENT_BLUE, fg=colors.white):
        super().__init__()
        self.diameter = diameter
        self.bg = bg
        self.fg = fg

    def wrap(self, availWidth, availHeight):
        return self.diameter, self.diameter

    def draw(self):
        c = self.canv
        r = self.diameter / 2
        c.saveState()
        c.setFillColor(self.bg)
        c.circle(r, r, r, fill=1, stroke=0)
        c.setFillColor(self.fg)
        c.setStrokeColor(self.fg)
        c.setLineWidth(1.1)
        # simple paper-plane triangle
        p = c.beginPath()
        p.moveTo(r - r * 0.55, r - r * 0.05)
        p.lineTo(r + r * 0.6, r + r * 0.42)
        p.lineTo(r - r * 0.15, r + r * 0.08)
        p.lineTo(r - r * 0.55, r - r * 0.05)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        c.restoreState()


class DashedConnector(Flowable):
    """Dashed horizontal line with a small plane-circle icon centered,
    used between departure/arrival airport blocks."""

    def __init__(self, width, height=18, color=BORDER, icon_color=ACCENT_BLUE):
        super().__init__()
        self.width = width
        self.height = height
        self.color = color
        self.icon_color = icon_color

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        y = self.height / 2
        c.saveState()
        c.setStrokeColor(self.color)
        c.setLineWidth(1)
        c.setDash(3, 3)
        c.line(0, y, self.width, y)
        c.restoreState()
        r = 8
        cx = self.width / 2
        c.saveState()
        c.setFillColor(colors.white)
        c.setStrokeColor(self.color)
        c.setLineWidth(1)
        c.circle(cx, y, r, fill=1, stroke=1)
        c.setFillColor(self.icon_color)
        p = c.beginPath()
        p.moveTo(cx - r * 0.55, y - r * 0.05)
        p.lineTo(cx + r * 0.6, y + r * 0.42)
        p.lineTo(cx - r * 0.15, y + r * 0.08)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        c.restoreState()


class BagIcon(Flowable):
    """Simple suitcase icon inside a circle, for baggage panels."""

    def __init__(self, diameter=28, bg=PANEL_LIGHT, fg=ACCENT_BLUE):
        super().__init__()
        self.diameter = diameter
        self.bg = bg
        self.fg = fg

    def wrap(self, availWidth, availHeight):
        return self.diameter, self.diameter

    def draw(self):
        c = self.canv
        r = self.diameter / 2
        c.saveState()
        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER)
        c.setLineWidth(1)
        c.circle(r, r, r, fill=1, stroke=1)
        c.setStrokeColor(self.fg)
        c.setLineWidth(1.4)
        bw, bh = r * 0.9, r * 0.7
        bx, by = r - bw / 2, r - bh / 2 - r * 0.08
        c.roundRect(bx, by, bw, bh, 2, fill=0, stroke=1)
        c.line(r - bw * 0.18, by + bh, r - bw * 0.18, by + bh + r * 0.22)
        c.line(r + bw * 0.18, by + bh, r + bw * 0.18, by + bh + r * 0.22)
        c.line(r - bw * 0.18, by + bh + r * 0.22, r + bw * 0.18, by + bh + r * 0.22)
        c.line(bx, by + bh * 0.5, bx + bw, by + bh * 0.5)
        c.restoreState()


def _row_spacer_table(width, height):
    t = Table([[""]], colWidths=[width], rowHeights=[height])
    t.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _tight_table(rows, colwidth, gaps):
    """rows: list of flowables; gaps: list of gap-in-points BEFORE each row
    (len(gaps) == len(rows), first is usually 0)."""
    data = [[r] for r in rows]
    t = Table(data, colWidths=[colwidth])
    style = [
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]
    for i, gap in enumerate(gaps):
        if gap:
            style.append(("TOPPADDING", (0, i), (0, i), gap))
    t.setStyle(TableStyle(style))
    return t


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------
def _section_title(title: str):
    heading = Paragraph(_tracked(title.upper()), STYLE_SECTION_TITLE)
    divider = _row_spacer_table(CONTENT_WIDTH, 1)
    divider.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1, BORDER)]))
    return _tight_table([heading, divider], CONTENT_WIDTH, [0, 5])


def _header_block(data: dict):
    logo_cell = _tight_table(
        [Paragraph("SAFRNA", STYLE_LOGO), Paragraph(_tracked("TRAVEL AND TOURISM"), STYLE_TAGLINE)],
        CONTENT_WIDTH * 0.6, [0, 3],
    )
    logo_row = Table([[PlaneBadge(17), logo_cell]], colWidths=[21, CONTENT_WIDTH * 0.6 - 21])
    logo_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    status = data.get("booking_status", "None")
    is_confirmed = "CONFIRM" in status.upper()
    pill = StatusPill(status.upper(), STATUS_BG if is_confirmed else colors.HexColor("#FED7D7"),
                       STATUS_TEXT if is_confirmed else colors.HexColor("#C53030"))
    pill_wrapper = Table([[pill]], colWidths=[CONTENT_WIDTH * 0.4])
    pill_wrapper.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    right_col = _tight_table([Paragraph("E-TICKET RECEIPT", STYLE_RECEIPT_LABEL), pill_wrapper], CONTENT_WIDTH * 0.4, [0, 8])

    header = Table([[logo_row, right_col]], colWidths=[CONTENT_WIDTH * 0.6, CONTENT_WIDTH * 0.4])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return header


def _info_bar(data: dict, class_of_service: str, passenger_count: int):
    def cell(label, value):
        return _tight_table([Paragraph(_tracked(label), STYLE_BAR_LABEL), Paragraph(value, STYLE_BAR_VALUE)],
                             CONTENT_WIDTH / 4 - 12, [0, 4])

    row = Table(
        [[cell("BOOKING REF", data.get("booking_reference", "None")),
          cell("AIRLINE", data.get("operating_carrier", "None")),
          cell("CLASS", class_of_service or "None"),
          cell("PASSENGERS", str(passenger_count))]],
        colWidths=[CONTENT_WIDTH / 4] * 4,
    )
    row.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 13), ("BOTTOMPADDING", (0, 0), (-1, -1), 13),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    card = RoundedCard(row, CONTENT_WIDTH, pad=0, radius=9, bg=NAVY, shadow=True)
    return card


def _flight_card(seg: dict):
    dep_cluster = _tight_table([
        Paragraph(seg.get("departure_airport_code", "None"), STYLE_AIRPORT_CODE),
        Paragraph(f"{seg.get('departure_airport_name')}<br/>{('Terminal ' + seg['departure_terminal']) if seg.get('departure_terminal') not in (None, 'None') else 'Terminal: None'}", STYLE_AIRPORT_NAME),
    ], CONTENT_WIDTH * 0.36, [0, 2])
    dep_time_cluster = _tight_table([
        Paragraph(seg.get("departure_time", "None"), STYLE_BIG_TIME),
        Paragraph(seg.get("departure_date", "None"), STYLE_FLIGHT_DATE),
    ], CONTENT_WIDTH * 0.36, [0, 4])
    dep_col = _tight_table([dep_cluster, dep_time_cluster], CONTENT_WIDTH * 0.36, [0, 15])

    arr_code_line = seg.get("arrival_airport_code", "None")
    if seg.get("arrival_day_offset"):
        arr_code_line += f" <font size=9 color='#DC2626'>{seg.get('arrival_day_offset')}</font>"
    arr_cluster = _tight_table([
        Paragraph(arr_code_line, STYLE_AIRPORT_CODE),
        Paragraph(f"{seg.get('arrival_airport_name')}<br/>{('Terminal ' + seg['arrival_terminal']) if seg.get('arrival_terminal') not in (None, 'None') else 'Terminal: None'}", STYLE_AIRPORT_NAME),
    ], CONTENT_WIDTH * 0.36, [0, 2])
    arr_time_cluster = _tight_table([
        Paragraph(seg.get("arrival_time", "None"), STYLE_BIG_TIME),
        Paragraph(seg.get("arrival_date", "None"), STYLE_FLIGHT_DATE),
    ], CONTENT_WIDTH * 0.36, [0, 4])
    arr_col = _tight_table([arr_cluster, arr_time_cluster], CONTENT_WIDTH * 0.36, [0, 15])

    center = _tight_table([
        Paragraph("NON-STOP", STYLE_NONSTOP),
        DashedConnector(CONTENT_WIDTH * 0.2),
        Paragraph(f"Duration: {seg.get('duration', 'None')}", STYLE_DURATION),
    ], CONTENT_WIDTH * 0.2, [0, 4, 4])

    route = Table([[dep_col, center, arr_col]], colWidths=[CONTENT_WIDTH * 0.36, CONTENT_WIDTH * 0.2, CONTENT_WIDTH * 0.36])
    route.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    meta_parts = [f"<b>Flight:</b> {seg.get('flight_number')}", f"<b>Class:</b> {seg.get('class')}"]
    if seg.get("aircraft") and seg.get("aircraft") != "None":
        meta_parts.append(f"<b>Aircraft:</b> {seg.get('aircraft')}")
    if seg.get("operated_by") and seg.get("operated_by") != "None":
        meta_parts.append(f"<b>Operated By:</b> {seg.get('operated_by')}")
    if seg.get("meal") and seg.get("meal") != "None":
        meta_parts.append(f"<b>Meal:</b> {seg.get('meal')}")
    meta = Paragraph("&nbsp;&nbsp;|&nbsp;&nbsp;".join(meta_parts), STYLE_SEGMENT_META)

    divider = _row_spacer_table(CONTENT_WIDTH, 1)
    divider.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1, BORDER)]))

    label = Paragraph(_tracked(seg.get("segment_label", "").upper()), STYLE_SEGMENT_LABEL)

    body = _tight_table([label, route, divider, meta], CONTENT_WIDTH - 14, [0, 6, 7, 4])
    return RoundedCard(body, CONTENT_WIDTH, pad=7, radius=7)


def _passenger_table(passengers: list, seat_route_labels: list):
    n_routes = len(seat_route_labels)
    seat_header = "SEAT" + (f" ({'/'.join(seat_route_labels)})" if n_routes else "")

    header_row = [
        Paragraph(_tracked("PASSENGER"), STYLE_TABLE_HEADER),
        Paragraph(_tracked("E-TICKET NO."), STYLE_TABLE_HEADER),
        Paragraph(_tracked("REWARDS"), STYLE_TABLE_HEADER),
        Paragraph(_tracked(seat_header), STYLE_TABLE_HEADER),
    ]
    rows = [header_row]
    if not passengers:
        rows.append([_p("None", STYLE_TABLE_VALUE_REG)] * 4)
    for p in passengers:
        seats = p.get("seat_assignments") or []
        seat_str = " / ".join(seats) if seats else "None"
        rows.append([
            _p(p.get("name"), STYLE_TABLE_VALUE),
            _p(p.get("electronic_ticket_no"), STYLE_TABLE_VALUE_REG),
            _p(p.get("rewards_program"), STYLE_TABLE_VALUE_REG),
            _p(seat_str, STYLE_TABLE_VALUE_REG),
        ])

    col_widths = [
        (CONTENT_WIDTH - 14) * 0.34, (CONTENT_WIDTH - 14) * 0.26,
        (CONTENT_WIDTH - 14) * 0.18, (CONTENT_WIDTH - 14) * 0.22,
    ]
    table = Table(rows, colWidths=col_widths)
    style = [
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, BORDER),
    ]
    for row_idx in range(1, len(rows) - 1):
        style.append(("LINEBELOW", (0, row_idx), (-1, row_idx), 0.5, BORDER))
    table.setStyle(TableStyle(style))
    return RoundedCard(table, CONTENT_WIDTH, pad=7, radius=7)


_LB_PAREN_RE = re.compile(r"\(\s*\d+(?:\.\d+)?\s*(?:lbs|lb|LBS|LB)\s*\)")
_LB_SLASH_KG_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:lbs|lb|LBS|LB)\s*/\s*(?=\d+(?:\.\d+)?\s*(?:kg|KG|Kg))")
_LB_ALONE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:lbs|lb|LBS|LB)\b")
_KG_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:KG|kg|Kg)")
_PIECE_RE = re.compile(r"(\d+)\s*(Piece|Pieces|PIECE|PIECES)")


def _kg_only(text: str) -> str:
    """Baggage weights must display in kg only. Handles three patterns:
    '(X lbs)' parentheticals next to a kg value -> dropped entirely;
    'Xlb/Ykg' combined format -> the lb part is dropped, kg value kept;
    standalone 'X lb'/'X lbs' with no kg nearby -> converted to kg.
    """
    if not text:
        return text
    text = _LB_PAREN_RE.sub("", text)
    text = _LB_SLASH_KG_RE.sub("", text)

    def _convert(m):
        lbs = float(m.group(1))
        kg = round(lbs * 0.453592)
        return f"{kg} kg"

    text = _LB_ALONE_RE.sub(_convert, text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def _headline_from_text(text: str):
    text = _kg_only(text or "")
    m = _KG_RE.search(text)
    if m:
        return f"{m.group(1)} KG"
    m = _PIECE_RE.search(text)
    if m:
        num, unit = m.groups()
        unit = "PC" if num == "1" else "PCS"
        return f"{num} {unit}"
    return "SEE DETAILS"


def _baggage_panels(checked_baggage: str, carry_on_rules: list):
    items = []
    if checked_baggage and checked_baggage != "None":
        items.append(("CHECKED BAGGAGE", _headline_from_text(checked_baggage), _kg_only(checked_baggage)))
    for rule in (carry_on_rules or []):
        if ":" in rule:
            label, desc = rule.split(":", 1)
        else:
            label, desc = "CARRY-ON", rule
        items.append((label.strip().upper(), _headline_from_text(rule), _kg_only(desc.strip())))

    if not items:
        items = [("BAGGAGE", "NONE", "No baggage information available.")]

    rows = []
    for i in range(0, len(items), 3):
        chunk = items[i:i + 3]
        col_w = CONTENT_WIDTH / 3 - 10
        cards = []
        for label, headline, desc in chunk:
            content = _tight_table([
                BagIcon(),
                Paragraph(_tracked(label), STYLE_BAG_LABEL),
                Paragraph(headline, STYLE_BAG_NUMBER),
                Paragraph(desc, STYLE_BAG_DESC),
            ], col_w - 20, [0, 8, 3, 4])
            wrapped = Table([[content]], colWidths=[col_w - 20])
            wrapped.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            cards.append(RoundedCard(wrapped, col_w, pad=7, radius=7, bg=PANEL_LIGHT, shadow=False, border=BORDER))
        while len(cards) < 3 and len(items) > 3:
            cards.append(Spacer(col_w, 1))
        row = Table([cards], colWidths=[CONTENT_WIDTH / len(cards)] * len(cards) if len(cards) < 3 else [CONTENT_WIDTH / 3] * 3)
        row.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        rows.append(row)
        if i + 3 < len(items):
            rows.append(Spacer(1, 7))
    return rows


def _page_background(canvas, doc):
    """Called at the START of each page (before flowables draw into the
    frame) so the light page background sits BEHIND all content."""
    canvas.saveState()
    canvas.setFillColor(PAGE_BG)
    canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
    canvas.restoreState()


def _footer(canvas, doc):
    """Called at final save() time (after content), but only paints the
    bottom footer strip — never the full page — so it can't cover content
    drawn earlier in that page's stream."""
    canvas.saveState()
    footer_h = 60
    canvas.setFillColor(colors.HexColor("#EDF1F5"))
    canvas.rect(0, 0, PAGE_WIDTH, footer_h, fill=1, stroke=0)
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.75)
    canvas.line(MARGIN, footer_h, PAGE_WIDTH - MARGIN, footer_h)

    text = canvas.beginText(MARGIN, footer_h - 14)
    text.setFont("Lato-Bold", 8.5)
    text.setFillColor(NAVY)
    text.textLine("Important Travel Information:")
    text.setFont("Lato", 7.5)
    text.setFillColor(MUTED)
    for line in [
        "\u2022 Please arrive at the airport at least 3 hours before departure for international flights.",
        "\u2022 Ensure your travel documents (passport, visa) are valid for the entire duration of your trip.",
        "\u2022 Baggage allowances and fare conditions are subject to the operating carrier's policy.",
    ]:
        text.textLine(line)
    canvas.drawText(text)

    canvas.setFont("Lato-Bold", 8.5)
    canvas.setFillColor(NAVY)
    canvas.drawCentredString(PAGE_WIDTH / 2, 8, "Thank you for choosing Safrna")

    canvas.setFont("Lato", 7.5)
    canvas.setFillColor(MUTED)
    page_num = canvas.getPageNumber()
    total = getattr(canvas, "_total_pages", None)
    label = f"Page {page_num} of {total}" if total else f"Page {page_num}"
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 8, label)
    canvas.restoreState()


class _CountingCanvas(canvas_module.Canvas):
    """Two-pass canvas so the footer can show 'Page X of Y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states = []

    def showPage(self):
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self._total_pages = total
            self._footer_fn(self, self._doc_ref)
            super().showPage()
        super().save()


def build_ticket_pdf(data: dict) -> bytes:
    """Render the extracted ticket `data` dict into a PDF and return raw bytes."""
    buffer = BytesIO()

    footer_bottom_reserve = 48
    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=10 * mm, bottomMargin=footer_bottom_reserve,
    )
    frame = Frame(MARGIN, footer_bottom_reserve, CONTENT_WIDTH, PAGE_HEIGHT - 10 * mm - footer_bottom_reserve, id="main")

    def make_canvas(*args, **kwargs):
        c = _CountingCanvas(*args, **kwargs)
        c._footer_fn = _footer
        c._doc_ref = doc
        return c

    doc.addPageTemplates([PageTemplate(id="ticket", frames=[frame], onPage=_page_background)])

    segments = data.get("segments") or []
    passengers = data.get("passengers") or []
    class_of_service = segments[0].get("class") if segments else "None"

    story = []
    story.append(_header_block(data))
    story.append(Spacer(1, 11))
    story.append(_info_bar(data, class_of_service, len(passengers)))
    story.append(Spacer(1, 14))

    if segments:
        story.append(_section_title("Flight Itinerary"))
        story.append(Spacer(1, 3))
        for i, seg in enumerate(segments):
            story.append(KeepTogether(_flight_card(seg)))
            if i < len(segments) - 1:
                story.append(Spacer(1, 7))
        story.append(Spacer(1, 13))

    story.append(_section_title("Passenger Details"))
    story.append(Spacer(1, 3))
    story.append(_passenger_table(passengers, data.get("seat_route_labels") or []))
    story.append(Spacer(1, 13))

    story.append(_section_title("Baggage Allowance"))
    story.append(Spacer(1, 3))
    for flow in _baggage_panels(data.get("checked_baggage", "None"), data.get("carry_on_rules") or []):
        story.append(flow)

    doc.build(story, canvasmaker=make_canvas)
    return buffer.getvalue()