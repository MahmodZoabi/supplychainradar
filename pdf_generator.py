"""
pdf_generator.py — Professional consulting-style PDF risk report using xhtml2pdf.

Entrypoint:
    generate_pdf(df, result, news_articles, analysis) -> bytes
"""

from datetime import datetime, timezone
from io import BytesIO

from xhtml2pdf import pisa

# ── Colour palette ─────────────────────────────────────────────────────────
_SLATE_950 = "#020617"
_SLATE_900 = "#0f172a"
_SLATE_800 = "#1e293b"
_SLATE_700 = "#334155"
_SLATE_500 = "#64748b"
_SLATE_400 = "#94a3b8"
_SLATE_200 = "#e2e8f0"
_SLATE_100 = "#f1f5f9"
_SLATE_50  = "#f8fafc"
_WHITE     = "#ffffff"

_TEAL      = "#14b8a6"
_TEAL_D    = "#0d9488"
_TEAL_PALE = "#f0fdfa"

_RED       = "#ef4444"
_RED_PALE  = "#fef2f2"
_ORANGE    = "#f97316"
_ORANGE_PALE = "#fff7ed"
_YELLOW    = "#eab308"
_YELLOW_PALE = "#fefce8"
_GREEN     = "#22c55e"
_GREEN_PALE = "#f0fdf4"
_GRAY      = "#94a3b8"

_GRADE_COLOR = {"A": _GREEN,  "B": _TEAL,   "C": _YELLOW, "D": _ORANGE, "F": _RED}
_LEVEL_COLOR = {"High": _RED, "Critical": _RED, "Moderate": _YELLOW, "Low": _GREEN, "N/A": _GRAY}
_SEV_COLOR   = {"Critical": _RED, "High": _ORANGE, "Medium": _YELLOW, "Low": _GREEN}
_SEV_PALE    = {"Critical": _RED_PALE, "High": _ORANGE_PALE, "Medium": _YELLOW_PALE, "Low": _GREEN_PALE}
_RISK_COLOR  = {"red": _RED, "orange": _ORANGE, "yellow": _YELLOW, "green": _GREEN}
_RISK_LABEL  = {"red": "High Risk", "orange": "Elevated", "yellow": "Moderate", "green": "Low Risk"}


def _h(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _badge(label: str, bg: str, text_color: str = _WHITE) -> str:
    return (
        f'<span style="display:inline-block;padding:3px 9px;border-radius:3px;'
        f'font-size:8px;font-weight:700;letter-spacing:1px;text-transform:uppercase;'
        f'color:{text_color};background-color:{bg};">{_h(label)}</span>'
    )


def _bar(pct: float, color: str, height: int = 13) -> str:
    """Colored progress bar with track."""
    w = round(min(100.0, max(0.0, pct)), 1)
    return (
        f'<div style="background-color:{_SLATE_200};height:{height}px;width:100%;">'
        f'<div style="background-color:{color};height:{height}px;width:{w}%;"></div>'
        f'</div>'
    )


def _section_header(number: str, title: str) -> str:
    return (
        f'<table style="width:100%;border-collapse:collapse;margin-top:24px;margin-bottom:14px;">'
        f'<tr>'
        f'<td style="padding:0;border-bottom:2px solid {_TEAL};padding-bottom:6px;width:100%;">'
        f'<span style="font-size:8px;font-weight:700;color:{_TEAL};letter-spacing:2px;'
        f'text-transform:uppercase;margin-right:8px;">{_h(number)}</span>'
        f'<span style="font-size:13px;font-weight:800;color:{_SLATE_900};'
        f'letter-spacing:1px;text-transform:uppercase;">{_h(title)}</span>'
        f'</td>'
        f'</tr>'
        f'</table>'
    )


def _build_html(df, result: dict, news_articles: list, analysis: dict | None) -> str:
    now       = datetime.now(timezone.utc)
    date_str  = now.strftime("%B %d, %Y")
    time_str  = now.strftime("%H:%M UTC")
    score     = result.get("score", 0)
    grade     = result.get("grade", "?")
    gc        = _GRADE_COLOR.get(grade, _GRAY)
    comp      = result.get("components", {})
    relevant_news = [a for a in news_articles if a.get("affected_suppliers")]
    n_alerts  = len(relevant_news)
    grade_desc = {
        "A": "Excellent — well diversified",
        "B": "Good — minor vulnerabilities",
        "C": "Fair — notable risk exposure",
        "D": "Poor — significant risks present",
        "F": "Critical — immediate action needed",
    }.get(grade, "")

    # ── CSS ────────────────────────────────────────────────────────────────
    css = f"""
@page {{
    size: A4;
    margin: 0mm 0mm 18mm 0mm;
    @frame footer_frame {{
        -pdf-frame-content: page_footer;
        bottom: 0mm;
        margin-left: 16mm;
        margin-right: 16mm;
        height: 14mm;
    }}
}}
@page cover_page {{
    margin: 0mm;
}}
body {{
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10px;
    color: {_SLATE_800};
    line-height: 1.5;
}}
.content-wrap {{
    margin-left: 16mm;
    margin-right: 16mm;
    margin-top: 10mm;
}}
p {{ margin: 0 0 6px 0; }}
table {{ border-collapse: collapse; font-size: 10px; }}
.full-width {{ width: 100%; }}
.th-dark {{
    background-color: {_SLATE_800};
    color: {_SLATE_200};
    font-size: 8px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 7px 10px;
    text-align: left;
}}
.td-base {{ padding: 7px 10px; border-bottom: 1px solid {_SLATE_200}; vertical-align: middle; }}
.no-break {{ page-break-inside: avoid; }}
"""

    # ── Footer (rendered on every page via @frame) ─────────────────────────
    footer_div = f"""
<div id="page_footer">
  <table style="width:100%;border-collapse:collapse;">
    <tr>
      <td style="padding:4px 0;border-top:1px solid {_SLATE_200};
                 font-size:8px;color:{_SLATE_400};text-align:left;">
        SupplyChainRadar &nbsp;&#183;&nbsp; Confidential &nbsp;&#183;&nbsp; {date_str}
      </td>
      <td style="padding:4px 0;border-top:1px solid {_SLATE_200};
                 font-size:8px;color:{_SLATE_400};text-align:right;">
        Page <pdf:pagenumber /> of <pdf:pagecount />
      </td>
    </tr>
  </table>
</div>
"""

    # ── Cover page ─────────────────────────────────────────────────────────
    cover = f"""
<div style="background-color:{_SLATE_900};min-height:260mm;padding:18mm 16mm 14mm 16mm;
            page-break-after:always;">

  <!-- Logo bar -->
  <table style="width:100%;margin-bottom:14mm;border-collapse:collapse;">
    <tr>
      <td style="padding:0;">
        <span style="font-size:16px;font-weight:900;color:{_TEAL};">&#9830;</span>
        <span style="font-size:11px;font-weight:800;color:{_WHITE};
                     letter-spacing:3px;margin-left:8px;">SUPPLYCHAINRADAR</span>
      </td>
      <td style="padding:0;text-align:right;font-size:9px;color:{_SLATE_500};">
        {date_str} &nbsp;&#183;&nbsp; {time_str}
      </td>
    </tr>
  </table>

  <!-- Teal rule -->
  <div style="height:3px;background-color:{_TEAL};margin-bottom:10mm;"></div>

  <!-- Report title block -->
  <p style="font-size:9px;font-weight:700;letter-spacing:3px;
            text-transform:uppercase;color:{_SLATE_500};margin-bottom:4px;">
    RISK INTELLIGENCE REPORT
  </p>
  <p style="font-size:30px;font-weight:900;color:{_WHITE};line-height:1.1;margin-bottom:2mm;">
    Supply Chain<br/>Risk Assessment
  </p>
  <p style="font-size:10px;color:{_SLATE_400};margin-bottom:12mm;">
    {result.get("supplier_count", 0)} suppliers across
    {comp.get("geographic", {}).get("country_count", 0)} countries &nbsp;&#183;&nbsp;
    {result.get("total_spend_tracked_pct", 0)}% spend tracked
  </p>

  <!-- Score display -->
  <table style="width:100%;margin-bottom:10mm;border-collapse:collapse;">
    <tr>
      <!-- Big score number -->
      <td style="padding:0;width:50%;vertical-align:middle;">
        <p style="font-size:80px;font-weight:900;color:{_WHITE};
                  line-height:1;margin:0;letter-spacing:-2px;">
          {score:.0f}
        </p>
        <p style="font-size:11px;color:{_SLATE_400};margin:2px 0 0 4px;">out of 100</p>
      </td>
      <!-- Grade circle + description -->
      <td style="padding:0;width:50%;vertical-align:middle;text-align:right;">
        <table style="margin-left:auto;border-collapse:collapse;">
          <tr>
            <td style="padding:0;text-align:center;">
              <div style="display:inline-block;width:70px;height:70px;
                          border:5px solid {gc};border-radius:35px;
                          text-align:center;vertical-align:middle;
                          background-color:rgba(0,0,0,0);">
                <p style="font-size:40px;font-weight:900;color:{gc};
                           line-height:60px;margin:0;">{_h(grade)}</p>
              </div>
              <p style="font-size:10px;color:{_SLATE_400};margin-top:5px;">{_h(grade_desc)}</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>

  <!-- Teal rule -->
  <div style="height:1px;background-color:{_SLATE_700};margin-bottom:8mm;"></div>

  <!-- Stats bar -->
  <table style="width:100%;border-collapse:collapse;">
    <tr>
      <td style="padding:0 16px 0 0;vertical-align:top;width:33%;">
        <p style="font-size:22px;font-weight:800;color:{_WHITE};margin:0;">{result.get("supplier_count",0)}</p>
        <p style="font-size:8px;letter-spacing:2px;text-transform:uppercase;
                  color:{_SLATE_500};margin:2px 0 0 0;">Suppliers</p>
      </td>
      <td style="padding:0 16px;vertical-align:top;border-left:1px solid {_SLATE_700};width:33%;">
        <p style="font-size:22px;font-weight:800;color:{'#ef4444' if n_alerts > 0 else _WHITE};margin:0;">{n_alerts}</p>
        <p style="font-size:8px;letter-spacing:2px;text-transform:uppercase;
                  color:{_SLATE_500};margin:2px 0 0 0;">Active Alert{"s" if n_alerts != 1 else ""}</p>
      </td>
      <td style="padding:0 0 0 16px;vertical-align:top;border-left:1px solid {_SLATE_700};width:33%;">
        <p style="font-size:22px;font-weight:800;color:{_WHITE};margin:0;">{result.get("total_spend_tracked_pct",0)}%</p>
        <p style="font-size:8px;letter-spacing:2px;text-transform:uppercase;
                  color:{_SLATE_500};margin:2px 0 0 0;">Spend Tracked</p>
      </td>
    </tr>
  </table>

</div>
"""

    # ── Section 01: Risk Overview ──────────────────────────────────────────
    flags = result.get("top_flags", [])
    flag_cards = ""
    for f in flags:
        flag_cards += (
            f'<div class="no-break" style="border-left:4px solid {_ORANGE};'
            f'background-color:{_ORANGE_PALE};padding:9px 12px;margin-bottom:6px;">'
            f'<span style="font-size:11px;color:{_ORANGE_PALE};">&#9888;</span> '
            f'<span style="font-size:10px;color:{_SLATE_800};">{_h(f)}</span>'
            f'</div>'
        )
    if not flag_cards:
        flag_cards = f'<p style="color:{_SLATE_400};font-size:10px;">No critical flags identified.</p>'

    overview_section = f"""
{_section_header("01", "Risk Overview")}
{flag_cards}
"""

    # ── Section 02: Risk Components ────────────────────────────────────────
    comp_blocks = ""
    for key, c in comp.items():
        level     = c.get("level", "N/A")
        risk_pct  = round(c.get("risk_normalized", 0) * 100, 1)
        bc        = _LEVEL_COLOR.get(level, _GRAY)
        weight    = c.get("weight_pct", 0)
        label     = c.get("label", "")
        comp_blocks += f"""
<div class="no-break" style="margin-bottom:12px;padding:10px 12px;
     background-color:{_SLATE_50};border-left:3px solid {bc};">
  <table style="width:100%;border-collapse:collapse;margin-bottom:6px;">
    <tr>
      <td style="padding:0;font-size:11px;font-weight:700;color:{_SLATE_800};">{_h(label)}</td>
      <td style="padding:0;text-align:right;">{_badge(level, bc)}</td>
    </tr>
  </table>
  <table style="width:100%;border-collapse:collapse;">
    <tr>
      <td style="padding:0;width:90%;vertical-align:middle;padding-right:8px;">
        {_bar(risk_pct, bc)}
      </td>
      <td style="padding:0;width:10%;text-align:right;font-size:9px;
                 color:{_SLATE_500};font-weight:600;white-space:nowrap;">
        {risk_pct:.0f}%
      </td>
    </tr>
  </table>
  <p style="font-size:8px;color:{_SLATE_400};margin-top:4px;margin-bottom:0;">
    Weight in overall score: {weight}%
  </p>
</div>"""

    components_section = f"""
{_section_header("02", "Risk Components")}
{comp_blocks}
"""

    # ── Section 03: Geographic Concentration ──────────────────────────────
    geo = comp.get("geographic", {})
    hhi = geo.get("score", 0)
    geo_level = geo.get("level", "N/A")

    geo_rows = ""
    for i, (country, info) in enumerate(
        sorted((geo.get("breakdown") or {}).items(),
               key=lambda x: x[1].get("share_pct", 0), reverse=True)
    ):
        bg = _SLATE_50 if i % 2 == 0 else _WHITE
        share = info.get("share_pct", 0)
        bar_color = _RED if share > 40 else _ORANGE if share > 20 else _TEAL
        geo_rows += (
            f'<tr class="no-break" style="background-color:{bg};">'
            f'<td class="td-base" style="font-weight:600;">{_h(country)}</td>'
            f'<td class="td-base" style="text-align:right;">{info.get("spend_pct",0):.1f}%</td>'
            f'<td class="td-base" style="text-align:right;font-weight:600;">{share:.1f}%</td>'
            f'<td class="td-base" style="width:40%;">{_bar(share, bar_color, 10)}</td>'
            f'</tr>'
        )

    geo_section = f"""
{_section_header("03", "Geographic Concentration")}
<table style="width:100%;border-collapse:collapse;margin-bottom:10px;">
  <tr>
    <td style="padding:0;vertical-align:middle;">
      <span style="font-size:22px;font-weight:900;color:{_LEVEL_COLOR.get(geo_level,_GRAY)};">
        {hhi:.4f}
      </span>
      <span style="font-size:10px;color:{_SLATE_500};margin-left:6px;">HHI Index</span>
    </td>
    <td style="padding:0;text-align:right;vertical-align:middle;">
      {_badge(geo_level, _LEVEL_COLOR.get(geo_level, _GRAY))}
      <span style="font-size:9px;color:{_SLATE_400};margin-left:6px;">
        {geo.get("country_count",0)} countries
      </span>
    </td>
  </tr>
</table>
<table class="full-width" style="border-collapse:collapse;">
  <tr>
    <th class="th-dark" style="width:30%;">Country</th>
    <th class="th-dark" style="width:20%;text-align:right;">Spend</th>
    <th class="th-dark" style="width:20%;text-align:right;">Share</th>
    <th class="th-dark" style="width:30%;">Concentration</th>
  </tr>
  {geo_rows}
</table>
"""

    # ── Section 04: Supplier Detail ────────────────────────────────────────
    from risk_engine import get_supplier_risk_levels
    risk_levels = get_supplier_risk_levels(df)

    sup_rows = ""
    for i, (_, row) in enumerate(df.iterrows()):
        rc       = risk_levels[i]
        lt_days  = int(row["lead_time_days"])
        spend    = float(row["spend_pct"])
        bg       = _SLATE_50 if i % 2 == 0 else _WHITE

        if lt_days > 60:
            lt_cell = (f'<td class="td-base" style="text-align:right;font-weight:700;'
                       f'color:{_WHITE};background-color:{_RED};">{lt_days}d</td>')
        elif lt_days > 45:
            lt_cell = (f'<td class="td-base" style="text-align:right;font-weight:700;'
                       f'color:{_WHITE};background-color:{_ORANGE};">{lt_days}d</td>')
        else:
            lt_cell = f'<td class="td-base" style="text-align:right;">{lt_days}d</td>'

        dot_color = _RISK_COLOR[rc]
        sup_rows += (
            f'<tr class="no-break" style="background-color:{bg};">'
            f'<td class="td-base" style="font-weight:600;font-size:9px;">{_h(row["name"])}</td>'
            f'<td class="td-base" style="font-size:9px;">{_h(row["country"])}</td>'
            f'<td class="td-base" style="font-size:9px;">{_h(row["category"])}</td>'
            f'{lt_cell}'
            f'<td class="td-base" style="text-align:right;font-weight:600;">{spend:.1f}%</td>'
            f'<td class="td-base" style="text-align:center;">'
            f'<span style="color:{dot_color};font-size:11px;font-weight:900;">&#9679;</span> '
            f'<span style="font-size:8px;color:{dot_color};font-weight:700;">'
            f'{_RISK_LABEL[rc]}</span></td>'
            f'</tr>'
        )

    suppliers_section = f"""
{_section_header("04", "Supplier Detail")}
<p style="font-size:9px;color:{_SLATE_400};margin-bottom:10px;">
  Lead times &gt;60d shown in red, &gt;45d in orange.
  {len(df)} suppliers total.
</p>
<table class="full-width" style="border-collapse:collapse;">
  <tr>
    <th class="th-dark" style="width:22%;">Supplier</th>
    <th class="th-dark" style="width:15%;">Country</th>
    <th class="th-dark" style="width:22%;">Category</th>
    <th class="th-dark" style="width:10%;text-align:right;">Lead</th>
    <th class="th-dark" style="width:10%;text-align:right;">Spend</th>
    <th class="th-dark" style="width:21%;text-align:center;">Risk Level</th>
  </tr>
  {sup_rows}
</table>
"""

    # ── Section 05: Live News Alerts ───────────────────────────────────────
    news_section = ""
    if relevant_news:
        alert_cards = ""
        for a in relevant_news[:10]:
            sev       = a.get("severity", "Medium")
            sc        = _SEV_COLOR.get(sev, _GRAY)
            sp        = _SEV_PALE.get(sev, _SLATE_50)
            n_sup     = len(a.get("affected_suppliers", []))
            sup_names = ", ".join(
                s["name"] for s in a.get("affected_suppliers", [])[:3]
            )
            if n_sup > 3:
                sup_names += f" +{n_sup-3} more"
            dur = a.get("estimated_duration", "")
            imp = a.get("impact_type", "")
            summary = a.get("summary", "")[:180]
            spend_pct = a.get("affected_spend_pct", 0)
            source = str(a.get("source", "") or "").strip()

            alert_cards += f"""
<div class="no-break" style="border-left:5px solid {sc};background-color:{sp};
     padding:10px 14px;margin-bottom:8px;">
  <table style="width:100%;border-collapse:collapse;margin-bottom:6px;">
    <tr>
      <td style="padding:0;vertical-align:middle;">
        {_badge(sev, sc)}
        {(' <span style="font-size:8px;color:' + _SLATE_500 + ';margin-left:6px;">' + _h(imp) + '</span>') if imp else ''}
      </td>
      <td style="padding:0;text-align:right;font-size:8px;color:{_SLATE_400};">
        {_h(source)}{(' &nbsp;&#183;&nbsp; Est. ' + _h(dur)) if dur else ''}
      </td>
    </tr>
  </table>
  <p style="font-size:11px;font-weight:700;color:{_SLATE_800};margin-bottom:4px;line-height:1.3;">
    {_h(a.get("title","")[:100])}
  </p>
  {f'<p style="font-size:9px;color:{_SLATE_700};margin-bottom:5px;line-height:1.4;">{_h(summary)}</p>' if summary else ''}
  <table style="width:100%;border-collapse:collapse;">
    <tr>
      <td style="padding:0;font-size:9px;color:{sc};font-weight:600;">
        {n_sup} supplier{"s" if n_sup!=1 else ""} affected &nbsp;&#183;&nbsp; {spend_pct}% of spend
      </td>
      <td style="padding:0;text-align:right;font-size:9px;color:{_SLATE_500};">
        {_h(sup_names)}
      </td>
    </tr>
  </table>
</div>"""

        news_section = f"""
{_section_header("05", f"Live Disruption Alerts ({n_alerts})")}
{alert_cards}
"""

    # ── Section 06: AI Analysis ────────────────────────────────────────────
    ai_section = ""
    sec_num = "06" if relevant_news else "05"
    if analysis and analysis.get("narrative"):
        flags_items = "".join(
            f'<div class="no-break" style="display:block;padding:5px 0 5px 12px;'
            f'border-bottom:1px solid {_SLATE_200};">'
            f'<span style="font-size:9px;color:{_ORANGE};margin-right:6px;">&#9654;</span>'
            f'<span style="font-size:10px;color:{_SLATE_700};">{_h(f)}</span>'
            f'</div>'
            for f in (analysis.get("flags") or [])
        )
        action_items = "".join(
            f'<div class="no-break" style="display:block;padding:6px 0 6px 12px;'
            f'border-bottom:1px solid {_SLATE_200};">'
            f'<span style="font-size:10px;font-weight:800;color:{_TEAL};margin-right:8px;">{i+1}.</span>'
            f'<span style="font-size:10px;color:{_SLATE_800};">{_h(a)}</span>'
            f'</div>'
            for i, a in enumerate(analysis.get("actions") or [])
        )
        ai_section = f"""
{_section_header(sec_num, "AI Risk Narrative")}
<div style="border-left:4px solid {_TEAL};background-color:{_TEAL_PALE};
            padding:12px 16px;margin-bottom:14px;">
  <p style="font-size:10.5px;color:#134e4a;line-height:1.65;margin:0;">
    {_h(analysis["narrative"])}
  </p>
</div>
{('<p style="font-size:11px;font-weight:700;color:' + _SLATE_800 + ';margin:12px 0 6px;">Key Observations</p>' + flags_items) if flags_items else ''}
{('<p style="font-size:11px;font-weight:700;color:' + _SLATE_800 + ';margin:12px 0 6px;">Recommended Actions</p>' + action_items) if action_items else ''}
"""

    # ── Assemble ───────────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <style>{css}</style>
</head>
<body>
{footer_div}
{cover}
<div class="content-wrap">
{overview_section}
{components_section}
{geo_section}
{suppliers_section}
{news_section}
{ai_section}
</div>
</body>
</html>"""


def generate_pdf(df, result: dict, news_articles: list, analysis: dict | None) -> bytes:
    """Render the risk report HTML and convert to PDF bytes via xhtml2pdf."""
    html = _build_html(df, result, news_articles, analysis)
    buf = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=buf)
    if pisa_status.err:
        raise RuntimeError(f"PDF generation failed: {pisa_status.err}")
    return buf.getvalue()
