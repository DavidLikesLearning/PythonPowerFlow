"""
generate_demo_pdf.py — Build an improved David_OPFs_demo.pdf from fresh CLI outputs.

Run with:  python3 generate_demo_pdf.py

Reads:  wb5_demo_plots/*.png
Writes: David_OPFs_demo.pdf
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
PLOTS = BASE / "wb5_demo_plots"
OUT_PDF = BASE / "David_OPFs_demo.pdf"
GITHUB_URL = "https://github.com/DavidLikesLearning/PythonPowerFlow/tree/DavidProject"

# ── Colours ───────────────────────────────────────────────────────────────────
BLUE = colors.HexColor("#1a4e8c")
GREY = colors.HexColor("#555555")
BOX_BG = colors.HexColor("#fff8e8")
BOX_BORDER = colors.HexColor("#c8a020")

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm
CONTENT_W = PAGE_W - 2 * MARGIN


# ── Styles ────────────────────────────────────────────────────────────────────
def _styles() -> dict:
    title = ParagraphStyle("T", fontName="Helvetica-Bold", fontSize=20,
                           textColor=BLUE, spaceAfter=4, alignment=TA_CENTER)
    subtitle = ParagraphStyle("ST", fontName="Helvetica", fontSize=11,
                              textColor=GREY, spaceAfter=2, alignment=TA_CENTER)
    link = ParagraphStyle("LK", fontName="Helvetica", fontSize=9,
                          textColor=BLUE, spaceAfter=10, alignment=TA_CENTER)
    body = ParagraphStyle("BD", fontName="Helvetica", fontSize=9.5, leading=14,
                          textColor=colors.black, spaceAfter=6, alignment=TA_JUSTIFY)
    section = ParagraphStyle("SC", fontName="Helvetica-Bold", fontSize=12,
                             textColor=BLUE, spaceBefore=10, spaceAfter=4)
    caption = ParagraphStyle("CP", fontName="Helvetica-Oblique", fontSize=8.5,
                             textColor=colors.HexColor("#444444"), spaceAfter=10,
                             alignment=TA_CENTER, leading=12)
    callout = ParagraphStyle("CL", fontName="Helvetica", fontSize=9, leading=13,
                             textColor=colors.HexColor("#3a3000"), backColor=BOX_BG,
                             borderColor=BOX_BORDER, borderWidth=1, borderPadding=6,
                             spaceAfter=10, alignment=TA_JUSTIFY)
    bullet = ParagraphStyle("BL", fontName="Helvetica", fontSize=9, leading=13,
                            textColor=colors.black, spaceAfter=2, leftIndent=12)
    bullet_bold = ParagraphStyle("BLB", fontName="Helvetica-Bold", fontSize=9, leading=13,
                                 textColor=colors.HexColor("#1a4e8c"), spaceAfter=1, leftIndent=12)
    code_inline = ParagraphStyle("CI", fontName="Courier", fontSize=9, leading=13,
                                 textColor=colors.HexColor("#2c2c2c"), spaceAfter=6,
                                 backColor=colors.HexColor("#f0f0f0"),
                                 leftIndent=16, rightIndent=8, borderPadding=4)
    footer = ParagraphStyle("FT", fontName="Helvetica", fontSize=8.5,
                            textColor=BLUE, alignment=TA_CENTER, spaceBefore=4)
    return dict(title=title, subtitle=subtitle, link=link, body=body,
                section=section, caption=caption, callout=callout,
                bullet=bullet, bullet_bold=bullet_bold, code_inline=code_inline,
                footer=footer)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _hr():
    return HRFlowable(width="100%", thickness=0.5,
                      color=colors.HexColor("#cccccc"), spaceAfter=8)


def _fit(path: Path, max_w: float, max_h: float) -> Image:
    im = PILImage.open(path)
    w, h = im.size
    scale = min(max_w / w, max_h / h)
    return Image(str(path), width=w * scale, height=h * scale)


def _side_by_side(left: Image, right: Image) -> Table:
    """Place two images in a single-row, two-column layout cell."""
    half = (CONTENT_W - 0.3 * cm) / 2
    tbl = Table([[left, right]], colWidths=[half, half])
    tbl.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    return tbl


# ── Pages ─────────────────────────────────────────────────────────────────────
def _page1(S: dict) -> list:
    story = [Spacer(1, 0.3 * cm)]

    # Title
    story.append(Paragraph("PythonPowerFlow — Interactive OPF Demo", S["title"]))
    story.append(Paragraph("WB5 Five-Bus Case · All Solvers · All Metrics", S["subtitle"]))
    story.append(Paragraph(
        f'<link href="{GITHUB_URL}" color="#1a4e8c">{GITHUB_URL}</link>', S["link"]))
    story.append(_hr())

    # Brief description
    story.append(Paragraph(
        "PythonPowerFlow compares five OPF solvers on standard test networks using an "
        "interactive CLI (<b>my_opfs.py</b>). The WB5 network (Bukhsh et al. 2013) is the "
        "canonical example of a non-exact SOCP relaxation: the cheap generator at Bus05 "
        "($1/MWh) is only reachable via two high-impedance lines, creating a 41% duality "
        "gap between the SOCP lower bound ($740/h) and the true AC optimum ($1,256/h).",
        S["body"],
    ))

    story.append(Paragraph("Solvers run:  "
        "Project SOCP (OPF) · Project DC OPF · Circuits NR · Panda DC OPF · Panda AC OPF",
        ParagraphStyle("BDC", fontName="Helvetica", fontSize=9, textColor=GREY,
                       spaceAfter=10, alignment=TA_CENTER)))

    story.append(_hr())

    # Figure 1 — voltages
    story.append(Paragraph("Bus Voltage Magnitudes", S["section"]))
    story.append(_fit(PLOTS / "fig_voltages.png", CONTENT_W, 10 * cm))
    story.append(Paragraph(
        "Figure 1. Bus voltage magnitudes (pu). SOCP pushes Bus04–05 to the 1.5 pu upper "
        "bound; Panda AC OPF finds the physical solution (Bus04 = 0.59 pu, Bus05 = 0.64 pu); "
        "DC solvers fix all voltages at 1.0 pu.",
        S["caption"]))

    # Figure 2 — angles
    story.append(Paragraph("Bus Voltage Angles", S["section"]))
    story.append(_fit(PLOTS / "fig_angles.png", CONTENT_W, 10 * cm))
    story.append(Paragraph(
        "Figure 2. Voltage angles (°). SOCP and DC OPF show unrealistically large spreads "
        "(Bus05 up to +99°) reflecting relaxed voltages. NR and AC OPF produce physically "
        "consistent negative angles.",
        S["caption"]))

    story.append(PageBreak())
    return story


def _page2(S: dict) -> list:
    story = []

    story.append(Paragraph("Duality Gap & SOCP Tightness", S["section"]))
    story.append(Paragraph(
        "Branch tightness τ = |W_ij|² / (W_ii·W_jj) measures SOC slack per branch. "
        "τ = 1 everywhere is necessary but <i>not sufficient</i> for exactness on meshed "
        "networks — loop residuals must also be zero.",
        S["body"],
    ))

    # Figures 3 & 4 side by side
    half = (CONTENT_W - 0.3 * cm) / 2
    fig_obj = _fit(PLOTS / "fig_objectives.png", half, 10 * cm)
    fig_tau = _fit(PLOTS / "fig_tightness.png", half, 10 * cm)
    story.append(_side_by_side(fig_obj, fig_tau))
    story.append(Paragraph(
        "Figure 3 (left). Objective values ($/h): SOCP ($740) and DC OPF ($325) are lower "
        "bounds; Panda AC OPF ($1,256) is the true AC optimum — 41% duality gap. "
        "Figure 4 (right). Per-branch SOC tightness τ: all 6 branches reach τ = 1 "
        "(gap &lt; 3×10⁻⁹) — the relaxation is tight everywhere.",
        S["caption"]))

    # Key insight callout
    story.append(Paragraph(
        "<b>WB5 key result — τ = 1 everywhere, yet 41% duality gap:</b><br/>"
        "All 6 SOC constraints are active, but loop residuals (L04-05: −1.58°, "
        "L02-03: +0.37°) reveal phase inconsistency around the two fundamental cycles. "
        "The W matrix is not globally rank-1 — the SOCP optimum is AC-infeasible. "
        "This is the canonical illustration that τ = 1 is <b>necessary but not sufficient</b> "
        "for SOCP exactness on meshed networks.",
        S["callout"],
    ))

    story.append(PageBreak())
    return story


def _page3(S: dict) -> list:
    story = []

    # Figure 5 — branch P
    story.append(Paragraph("Branch Active Power Flows", S["section"]))
    story.append(_fit(PLOTS / "fig_branch_p.png", CONTENT_W, 11 * cm))
    story.append(Paragraph(
        "Figure 5. Active power P_from (pu). SOCP and DC OPF show negative flows on "
        "L02-04 and L03-05 (cheap generator pulling power backwards through high-impedance "
        "lines). NR and AC OPF show positive flows at the physical operating point.",
        S["caption"]))

    # Figure 6 — branch Q
    story.append(Paragraph("Branch Reactive Power Flows", S["section"]))
    story.append(_fit(PLOTS / "fig_branch_q.png", CONTENT_W, 11 * cm))
    story.append(Paragraph(
        "Figure 6. Reactive power Q_from (pu). DC solvers return Q = 0 by definition. "
        "SOCP and AC solvers show substantial reactive flows on L01-02 and L01-03 "
        "(slack bus supplies reactive demand). Circuits NR shows negative Q on L02-04 "
        "and L03-05 at the physical operating point.",
        S["caption"]))

    story.append(_hr())
    story.append(Paragraph(
        f'Source code: <link href="{GITHUB_URL}" color="#1a4e8c">{GITHUB_URL}</link>',
        S["footer"]))

    return story


# ── Main ──────────────────────────────────────────────────────────────────────
def build_pdf():
    print(f"Writing: {OUT_PDF}")
    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title="PythonPowerFlow — Interactive OPF Demo",
        author="David Jose Florez Rodriguez",
        subject="WB5 five-bus OPF comparison",
    )
    S = _styles()
    story = _page1(S) + _page2(S) + _page3(S)
    doc.build(story)
    print(f"Done → {OUT_PDF}")


if __name__ == "__main__":
    build_pdf()
