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
                           textColor=BLUE, spaceBefore=6, spaceAfter=10, leading=26,
                           alignment=TA_CENTER)
    subtitle = ParagraphStyle("ST", fontName="Helvetica", fontSize=11,
                              textColor=GREY, spaceBefore=2, spaceAfter=6, leading=16,
                              alignment=TA_CENTER)
    link = ParagraphStyle("LK", fontName="Helvetica", fontSize=9,
                          textColor=BLUE, spaceAfter=10, alignment=TA_CENTER)
    body = ParagraphStyle("BD", fontName="Helvetica", fontSize=9.5, leading=14,
                          textColor=colors.black, spaceAfter=6, alignment=TA_JUSTIFY)
    section = ParagraphStyle("SC", fontName="Helvetica-Bold", fontSize=12,
                             textColor=BLUE, spaceBefore=10, spaceAfter=4,
                             keepWithNext=True)
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
                                 textColor=colors.HexColor("#2c2c2c"),
                                 spaceBefore=6, spaceAfter=6,
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


FIG_W = CONTENT_W * 0.45


def _fit(path: Path, max_w: float = FIG_W, max_h: float = 99 * cm) -> Image:
    im = PILImage.open(path)
    w, h = im.size
    scale = min(max_w / w, max_h / h)
    img = Image(str(path), width=w * scale, height=h * scale)
    img.hAlign = "CENTER"
    return img


def _side_by_side(left: Image, right: Image) -> Table:
    """Place two images side-by-side, each at FIG_W, centred on the page."""
    pad = (CONTENT_W - 2 * FIG_W) / 2
    tbl = Table([[left, right]], colWidths=[FIG_W + pad, FIG_W + pad])
    tbl.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    return tbl


# ── Pages ─────────────────────────────────────────────────────────────────────
def _usage_page(S: dict) -> list:
    """Page 1 — how to use my_opfs.py."""
    story = [Spacer(1, 0.2 * cm)]

    story.append(Paragraph("Using my_opfs.py", S["title"]))
    story.append(Paragraph("Interactive OPF Solver Comparison CLI", S["subtitle"]))
    story.append(Paragraph(
        f'<link href="{GITHUB_URL}" color="#1a4e8c">{GITHUB_URL}</link>', S["link"]))
    story.append(_hr())

    # Quick start
    story.append(Paragraph("Quick Start", S["section"]))
    story.append(Paragraph("python3 my_opfs.py", S["code_inline"]))
    story.append(Paragraph(
        "Launches a five-step interactive session. All heavy solver imports happen after "
        "the prompts, so the menu appears instantly. Press Ctrl-C at any prompt to exit.",
        S["body"]))

    # Step 1
    story.append(Paragraph("Step 1 — Choose a Grid", S["section"]))
    grids = [
        ("1. IEEE 14-bus", "14-bus meshed network. SOCP runs in PF mode (compare to NR). "
         "tau ~ 1 everywhere but loop residuals up to 4.3° — shows tau = 1 does not imply exactness."),
        ("2. WB5", "5-bus Bukhsh 2013 network. SOCP runs in OPF mode. "
         "41% duality gap — canonical non-exact SOCP example."),
        ("3. Case22loop (uniform)", "22-bus ring, all generators at $2/MWh. "
         "SOCP exact (zero duality gap, loop residual = 0°)."),
        ("4. Case22loop (asymmetric)", "22-bus ring, cheap arc $1/MWh vs expensive arc $4/MWh. "
         "Two distinct local AC optima; SOCP still exact."),
    ]
    for label, desc in grids:
        story.append(Paragraph(f"<b>{label}</b> — {desc}", S["bullet"]))
    story.append(Spacer(1, 0.2 * cm))

    # Step 2
    story.append(Paragraph("Step 2 — Choose Solvers", S["section"]))
    story.append(Paragraph(
        "Enter comma-separated numbers (e.g. <font face='Courier'>1,3,5</font>) "
        "or press Enter to run all five:", S["body"]))
    solvers = [
        "1. Circuits NR — Newton-Raphson AC power flow (feasibility, no objective)",
        "2. Project DC OPF — cvxpy LP, lossless DC approximation",
        "3. Project SOCP — Jabr SOCP relaxation (PF or OPF mode, fixed per grid)",
        "4. Panda DC OPF — pandapower DC OPF (uses 1/x susceptance)",
        "5. Panda AC OPF — PYPOWER interior-point AC OPF (slowest, most accurate)",
    ]
    story.append(ListFlowable(
        [ListItem(Paragraph(s, S["bullet"]), leftIndent=20, bulletColor=BLUE) for s in solvers],
        bulletType="bullet", leftIndent=8, bulletFontSize=7,
    ))
    story.append(Spacer(1, 0.2 * cm))

    # Step 3
    story.append(Paragraph("Step 3 — Generator Costs", S["section"]))
    story.append(Paragraph(
        "Default costs are shown for the chosen grid. Enter <b>Y</b> to accept them, "
        "or <b>N</b> to supply custom values in one of two ways:", S["body"]))
    story.append(Paragraph(
        "Comma-separated list — one number per generator in the displayed order, e.g. "
        "<font face='Courier'>4, 1</font> for WB5 (GenSlack, GenPV).", S["bullet"]))
    story.append(Paragraph(
        "CSV file — either a single-column file (costs in order) or a two-column "
        "<font face='Courier'>gen_name,cost</font> file with an optional header row.",
        S["bullet"]))
    story.append(Spacer(1, 0.2 * cm))

    # Step 4
    story.append(Paragraph("Step 4 — Metrics to Display", S["section"]))
    story.append(Paragraph(
        "Enter comma-separated numbers or press Enter for all nine:", S["body"]))
    metrics = [
        "1. Voltage magnitudes (pu)",
        "2. Voltage angles (°)",
        "3. Branch P flows — from-end active power (pu)",
        "4. Branch Q flows — from-end reactive power (pu, zero for DC solvers)",
        "5. Objective value ($/h) — N/A for NR",
        "6. Convergence status",
        "7. Solve time (s)",
        "8. SOCP tightness tau per branch — always from the SOCP result",
        "9. Loop residuals (°) — phase inconsistency around fundamental cycles",
    ]
    story.append(ListFlowable(
        [ListItem(Paragraph(m, S["bullet"]), leftIndent=20, bulletColor=BLUE) for m in metrics],
        bulletType="bullet", leftIndent=8, bulletFontSize=7,
    ))
    story.append(Spacer(1, 0.2 * cm))

    # Step 5
    story.append(Paragraph("Step 5 — Save Outputs", S["section"]))
    story.append(Paragraph(
        "<b>CSV</b> — four-section comparison file: (1) solver summary, (2) bus voltages, "
        "(3) branch flows, (4) SOCP tightness and loop residuals. "
        "Default filename is <font face='Courier'>&lt;grid&gt;_comparison.csv</font>.",
        S["bullet"]))
    story.append(Paragraph(
        "<b>Plots</b> — PNG figures saved to a chosen directory: "
        "<font face='Courier'>fig_voltages.png</font>, "
        "<font face='Courier'>fig_angles.png</font>, "
        "<font face='Courier'>fig_branch_p.png</font>, "
        "<font face='Courier'>fig_branch_q.png</font>, "
        "<font face='Courier'>fig_objectives.png</font>, "
        "<font face='Courier'>fig_tightness.png</font>.",
        S["bullet"]))

    story.append(Spacer(1, 0.3 * cm))
    story.append(_hr())

    # Example sessions
    story.append(Paragraph("Example Sessions", S["section"]))
    examples = [
        ("Check the WB5 duality gap",
         "Step 1: 2  ·  Step 2: 3,5  ·  Step 3: Y  ·  Step 4: 5,8,9  ·  Step 5: Y / N"),
        ("Verify SOCP vs NR on IEEE 14-bus",
         "Step 1: 1  ·  Step 2: 1,3  ·  Step 3: Y  ·  Step 4: 1,6,7  ·  Step 5: N / N"),
        ("Run asymmetric ring with all solvers",
         "Step 1: 4  .  Step 2: [Enter]  .  Step 3: Y  .  Step 4: [Enter]  .  Step 5: Y / Y"),
    ]
    for title_ex, inputs in examples:
        story.append(Paragraph(f"<b>{title_ex}</b>", S["bullet_bold"]))
        story.append(Paragraph(inputs,
                               ParagraphStyle("EX", fontName="Courier", fontSize=8,
                                              textColor=colors.HexColor("#2c2c2c"),
                                              spaceBefore=4, spaceAfter=8,
                                              leftIndent=24,
                                              backColor=colors.HexColor("#f4f4f4"),
                                              borderPadding=3)))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Voltage bounds are set automatically per grid: WB5 uses [0.5, 1.5] pu "
        "(natural operating point is below 0.95 pu); all other grids use [0.95, 1.05] pu.",
        S["body"]))

    story.append(PageBreak())
    return story


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
    story.append(_fit(PLOTS / "fig_voltages.png"))
    story.append(Paragraph(
        "Figure 1. Bus voltage magnitudes (pu). SOCP pushes Bus04–05 to the 1.5 pu upper "
        "bound; Panda AC OPF finds the physical solution (Bus04 = 0.59 pu, Bus05 = 0.64 pu); "
        "DC solvers fix all voltages at 1.0 pu.",
        S["caption"]))

    # Figure 2 — angles
    story.append(Paragraph("Bus Voltage Angles", S["section"]))
    story.append(_fit(PLOTS / "fig_angles.png"))
    story.append(Paragraph(
        "Figure 2. Voltage angles (°). SOCP and DC OPF show unrealistically large spreads "
        "(Bus05 up to +99°) reflecting relaxed voltages. NR and Panda AC OPF produce "
        "physically consistent negative angles.",
        S["caption"]))
    story.append(Paragraph(
        "<b>Why do Project DC OPF and Panda DC OPF give different angles?</b> "
        "Both use the same lossless DC approximation (V = 1 pu, linearised power balance) "
        "but differ in how they compute the line susceptance b_ij. "
        "Project DC OPF uses <i>b_ij = x / (r&#178; + x&#178;)</i> — the imaginary part of "
        "the series admittance y = 1 / (r + jx), which is exact for the DC model. "
        "Panda DC OPF uses <i>b_ij = 1 / x</i> — ignoring resistance entirely. "
        "On WB5's high-impedance lines (r = 0.55, x = 0.90 pu) the ratio r/x = 0.61, so "
        "the two susceptance values differ significantly: "
        "b = 0.90 / (0.55&#178; + 0.90&#178;) = 0.865 pu vs. 1/0.90 = 1.111 pu. "
        "Pandapower's larger susceptances make the network appear stiffer, "
        "which compresses the angle spread (Bus05: +72° vs. +99° for Project DC OPF). "
        "Both are valid DC approximations; the discrepancy vanishes on low-r/x lines.",
        S["body"]))

    story.append(PageBreak())
    return story


def _page2(S: dict) -> list:
    story = []

    story.append(Paragraph("Duality Gap & SOCP Tightness", S["section"]))
    story.append(Paragraph(
        "Branch tightness tau = |W_ij|&#178; / (W_ii * W_jj) measures SOC slack per branch. "
        "tau = 1 everywhere is necessary but <i>not sufficient</i> for exactness on meshed "
        "networks — loop residuals must also be zero.",
        S["body"],
    ))

    # Figures 3 & 4 side by side
    fig_obj = _fit(PLOTS / "fig_objectives.png")
    fig_tau = _fit(PLOTS / "fig_tightness.png")
    story.append(_side_by_side(fig_obj, fig_tau))
    story.append(Paragraph(
        "Figure 3 (left). Objective values ($/h): SOCP ($740) and DC OPF ($325) are lower "
        "bounds; Panda AC OPF ($1,256) is the true AC optimum — 41% duality gap. "
        "Figure 4 (right). Per-branch SOC tightness tau: all 6 branches reach tau = 1 "
        "(gap &lt; 3e-9) — the relaxation is tight everywhere.",
        S["caption"]))

    # Key insight callout
    story.append(Paragraph(
        "<b>WB5 key result — tau = 1 everywhere, yet 41% duality gap:</b><br/>"
        "All 6 SOC constraints are active, but loop residuals (L04-05: -1.58°, "
        "L02-03: +0.37°) reveal phase inconsistency around the two fundamental cycles. "
        "The W matrix is not globally rank-1 — the SOCP optimum is AC-infeasible. "
        "This is the canonical illustration that tau = 1 is <b>necessary but not sufficient</b> "
        "for SOCP exactness on meshed networks.",
        S["callout"],
    ))

    story.append(PageBreak())
    return story


def _page3(S: dict) -> list:
    story = []

    # Figure 5 — branch P
    story.append(Paragraph("Branch Active Power Flows", S["section"]))
    story.append(_fit(PLOTS / "fig_branch_p.png"))
    story.append(Paragraph(
        "Figure 5. Active power P_from (pu). SOCP and DC OPF show negative flows on "
        "L02-04 and L03-05 (cheap generator pulling power backwards through high-impedance "
        "lines). NR and AC OPF show positive flows at the physical operating point.",
        S["caption"]))

    # Figure 6 — branch Q
    story.append(Paragraph("Branch Reactive Power Flows", S["section"]))
    story.append(_fit(PLOTS / "fig_branch_q.png"))
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
    story = _usage_page(S) + _page1(S) + _page2(S) + _page3(S)
    doc.build(story)
    print(f"Done → {OUT_PDF}")


if __name__ == "__main__":
    build_pdf()
