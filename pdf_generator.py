"""
pdf_generator.py — Generate a professional PDF risk report using xhtml2pdf.

Entrypoint:
    generate_pdf(df, result, news_articles, analysis) -> bytes
"""

from datetime import datetime, timezone
from io import BytesIO

from xhtml2pdf import pisa


# ── Colour palette (matches dashboard) ────────────────────────────────────
_TEAL   = "#14b8a6"
_TEAL_D = "#0d9488"
_RED    = "#ef4444"
_ORANGE = "#f97316"
_YELLOW = "#eab308"
_GREEN  = "#22c55e"
_GRAY   = "#94a3b8"

_GRADE_COLOR = {"A": _GREEN, "B": _TEAL, "C": _YELLOW, "D": _ORANGE, "F": _RED}
_LEVEL_COLOR = {"High": _RED, "Critical": _RED, "Moderate": _YELLOW, "Low": _GREEN, "N/A": _GRAY}
_SEV_COLOR   = {"Critical": _RED, "High": _ORANGE, "Medium": _YELLOW, "Low": _GREEN}


def _bar(pct: float, color: str, height: int = 8) -> str:
    """Inline HTML progress bar."""
    w = round(min(100.0, max(0.0, pct)), 1)
    return (
        f'<div style="background:#e2e8f0;border-radius:4px;height:{height}px;width:100%;">'
        f'<div style="background:{color};border-radius:4px;height:{height}px;width:{w}%;"></div>'
        f'</div>'
    )


def _risk_badge(level: str) -> str:
    color = _LEVEL_COLOR.get(level, _GRAY)
    label = level if level != "N/A" else "N/A"
    return (
        f'<span style="display:inline-block;padding:2px 7px;border-radius:4px;'
        f'font-size:10px;font-weight:600;color:#fff;background:{color};">{label}</span>'
    )


def _sev_badge(sev: str) -> str:
    color = _SEV_COLOR.get(sev, _GRAY)
    return (
        f'<span style="display:inline-block;padding:2px 7px;border-radius:4px;'
        f'font-size:9px;font-weight:700;color:#fff;background:{color};">{sev}</span>'
    )


def _build_html(df, result: dict, news_articles: list, analysis: dict | None) -> str:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%B %d, %Y")
    time_str = now.strftime("%H:%M UTC")
    score = result.get("score", 0)
    grade = result.get("grade", "?")
    grade_color = _GRADE_COLOR.get(grade, _GRAY)
    comp = result.get("components", {})
    n_alerts = len([a for a in news_articles if a.get("affected_suppliers")])

    # ── helpers ────────────────────────────────────────────────────────────
    def h(s: str) -> str:
        """HTML-escape."""
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def row_bg(i: int) -> str:
        return "#f8fafc" if i % 2 == 0 else "#ffffff"

    # ── CSS ────────────────────────────────────────────────────────────────
    css = f"""
    @page {{
        size: A4;
        margin: 18mm 16mm 18mm 16mm;
    }}
    body {{
        font-family: Helvetica, Arial, sans-serif;
        font-size: 11px;
        color: #1e293b;
        margin: 0;
        padding: 0;
        line-height: 1.45;
    }}
    h1 {{ font-size: 22px; font-weight: 800; margin: 0 0 4px; color: #0f172a; }}
    h2 {{ font-size: 13px; font-weight: 700; color: {_TEAL_D};
          border-bottom: 2px solid {_TEAL}; padding-bottom: 4px;
          margin: 18px 0 10px; text-transform: uppercase; letter-spacing: 1px; }}
    h3 {{ font-size: 11px; font-weight: 600; margin: 10px 0 4px; color: #334155; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 10px; }}
    th {{ background: #1e293b; color: #e2e8f0; font-weight: 600; padding: 5px 8px;
          text-align: left; font-size: 9px; text-transform: uppercase; letter-spacing: 1px; }}
    td {{ padding: 4px 8px; border-bottom: 1px solid #e2e8f0; vertical-align: middle; }}
    .cover-box {{
        background: #0f172a;
        color: #f1f5f9;
        padding: 32px 28px;
        border-radius: 8px;
        margin-bottom: 24px;
    }}
    .score-circle {{
        display: inline-block;
        width: 64px; height: 64px;
        border-radius: 50%;
        border: 5px solid {grade_color};
        text-align: center;
        line-height: 54px;
        font-size: 26px;
        font-weight: 900;
        color: {grade_color};
        background: rgba(255,255,255,.05);
        margin-right: 16px;
        vertical-align: middle;
    }}
    .score-num {{
        display: inline-block;
        font-size: 42px;
        font-weight: 900;
        color: #ffffff;
        vertical-align: middle;
        margin-right: 8px;
    }}
    .meta {{ font-size: 10px; color: #94a3b8; margin-top: 8px; }}
    .flag-item {{ background: #fff7ed; border-left: 3px solid {_ORANGE};
                  padding: 5px 8px; margin: 4px 0; border-radius: 0 4px 4px 0;
                  font-size: 10px; color: #431407; }}
    .action-item {{ padding: 4px 0; font-size: 10px; color: #1e293b; }}
    .action-num {{ color: {_TEAL}; font-weight: 700; margin-right: 6px; }}
    .narrative {{ background: #f0fdfa; border-left: 3px solid {_TEAL};
                  padding: 8px 12px; margin: 8px 0; border-radius: 0 6px 6px 0;
                  font-size: 10.5px; color: #134e4a; line-height: 1.6; }}
    .section-meta {{ font-size: 9px; color: #94a3b8; margin-bottom: 10px; }}
    .no-break {{ page-break-inside: avoid; }}
    """

    # ── Cover ──────────────────────────────────────────────────────────────
    cover = f"""
    <div class="cover-box">
      <div style="margin-bottom:20px;">
        <span style="color:{_TEAL};font-size:18px;font-weight:900;">◈</span>
        <span style="color:#e2e8f0;font-size:13px;font-weight:700;
                     letter-spacing:.08em;margin-left:8px;">SUPPLYCHAINRADAR</span>
      </div>
      <h1 style="color:#f8fafc;margin-bottom:6px;">Supply Chain Risk Report</h1>
      <p class="meta">{date_str} at {time_str} &nbsp;·&nbsp;
         {result.get("supplier_count",0)} suppliers &nbsp;·&nbsp;
         {result.get("total_spend_tracked_pct",0)}% spend tracked &nbsp;·&nbsp;
         {n_alerts} active alert{"s" if n_alerts != 1 else ""}
      </p>
      <div style="margin-top:20px;">
        <span class="score-num">{score:.0f}</span>
        <span class="score-circle">{h(grade)}</span>
        <span style="font-size:11px;color:#94a3b8;vertical-align:middle;">/ 100</span>
      </div>
      <p style="font-size:10px;color:#64748b;margin-top:6px;">
        {"Excellent — well diversified" if grade=="A" else
         "Good — minor vulnerabilities" if grade=="B" else
         "Fair — notable risk exposure" if grade=="C" else
         "Poor — significant risks present" if grade=="D" else
         "Critical — immediate action needed"}
      </p>
    </div>
    """

    # ── Top flags ─────────────────────────────────────────────────────────
    flags_html = ""
    if result.get("top_flags"):
        flags_html = "<h2>Top Risk Flags</h2>"
        for f in result["top_flags"]:
            flags_html += f'<div class="flag-item">&#9888; {h(f)}</div>'

    # ── Risk components ───────────────────────────────────────────────────
    comp_rows = ""
    for key, c in comp.items():
        level = c.get("level", "N/A")
        risk_pct = round(c.get("risk_normalized", 0) * 100, 1)
        bar_color = _LEVEL_COLOR.get(level, _GRAY)
        comp_rows += f"""
        <tr class="no-break">
          <td style="width:38%;font-weight:600;">{h(c.get("label",""))}</td>
          <td style="width:8%;text-align:center;">{c.get("weight_pct",0)}%</td>
          <td style="width:34%;">{_bar(risk_pct, bar_color)}</td>
          <td style="width:20%;text-align:center;">{_risk_badge(level)}</td>
        </tr>"""

    components_section = f"""
    <h2>Risk Components</h2>
    <table>
      <tr>
        <th style="width:38%;">Component</th>
        <th style="width:8%;text-align:center;">Weight</th>
        <th style="width:34%;">Risk Level</th>
        <th style="width:20%;text-align:center;">Rating</th>
      </tr>
      {comp_rows}
    </table>
    """

    # ── Geographic concentration ──────────────────────────────────────────
    geo = comp.get("geographic", {})
    geo_rows = ""
    for country, info in (geo.get("breakdown") or {}).items():
        geo_rows += (
            f'<tr><td>{h(country)}</td>'
            f'<td style="text-align:right;">{info.get("spend_pct",0):.1f}%</td>'
            f'<td style="text-align:right;">{info.get("share_pct",0):.1f}%</td>'
            f'<td>{_bar(info.get("share_pct",0), _TEAL, 6)}</td></tr>'
        )
    hhi_val = geo.get("score", 0)
    geo_section = f"""
    <h2>Geographic Concentration</h2>
    <p class="section-meta">HHI = {hhi_val:.4f} &nbsp;·&nbsp; {geo.get("country_count",0)} countries
       &nbsp;·&nbsp; Rating: {_risk_badge(geo.get("level","N/A"))}</p>
    <table>
      <tr>
        <th style="width:40%;">Country</th>
        <th style="width:20%;text-align:right;">Spend ($)</th>
        <th style="width:20%;text-align:right;">Share %</th>
        <th style="width:20%;">Concentration</th>
      </tr>
      {geo_rows}
    </table>
    """

    # ── Supplier table ─────────────────────────────────────────────────────
    from risk_engine import get_supplier_risk_levels
    _RISK_LABEL = {"red": "High Risk", "orange": "Elevated", "yellow": "Moderate", "green": "Low Risk"}
    _RISK_COLOR = {"red": _RED, "orange": _ORANGE, "yellow": _YELLOW, "green": _GREEN}
    risk_levels = get_supplier_risk_levels(df)
    sup_rows = ""
    for i, (_, row) in enumerate(df.iterrows()):
        rc = risk_levels[i]
        lt_style = f"color:{_ORANGE};font-weight:600;" if int(row["lead_time_days"]) > 45 else ""
        sup_rows += (
            f'<tr style="background:{row_bg(i)};">'
            f'<td style="font-weight:600;">{h(row["name"])}</td>'
            f'<td>{h(row["country"])}</td>'
            f'<td>{h(row["category"])}</td>'
            f'<td style="text-align:right;{lt_style}">{int(row["lead_time_days"])}d</td>'
            f'<td style="text-align:right;">{float(row["spend_pct"]):.1f}%</td>'
            f'<td style="text-align:center;">'
            f'<span style="color:{_RISK_COLOR[rc]};font-weight:700;font-size:9px;">'
            f'&#9679; {_RISK_LABEL[rc]}</span></td>'
            f'</tr>'
        )
    suppliers_section = f"""
    <h2>Supplier Detail</h2>
    <p class="section-meta">{len(df)} suppliers &nbsp;·&nbsp; lead times &gt;45d highlighted in orange</p>
    <table>
      <tr>
        <th style="width:24%;">Supplier</th>
        <th style="width:16%;">Country</th>
        <th style="width:22%;">Category</th>
        <th style="width:10%;text-align:right;">Lead</th>
        <th style="width:10%;text-align:right;">Spend</th>
        <th style="width:18%;text-align:center;">Risk</th>
      </tr>
      {sup_rows}
    </table>
    """

    # ── News alerts ────────────────────────────────────────────────────────
    relevant = [a for a in news_articles if a.get("affected_suppliers")]
    news_section = ""
    if relevant:
        alert_rows = ""
        for i, a in enumerate(relevant[:10]):
            n_sup = len(a.get("affected_suppliers", []))
            sup_names = ", ".join(s["name"] for s in a.get("affected_suppliers", [])[:3])
            if len(a.get("affected_suppliers", [])) > 3:
                sup_names += f' +{len(a["affected_suppliers"])-3} more'
            alert_rows += (
                f'<tr style="background:{row_bg(i)};">'
                f'<td style="width:14%;text-align:center;">{_sev_badge(a.get("severity","?"))}</td>'
                f'<td style="width:38%;font-weight:600;">{h(a.get("title","")[:70])}</td>'
                f'<td style="width:30%;font-size:9px;color:#475569;">{h(a.get("summary","")[:90])}</td>'
                f'<td style="width:18%;font-size:9px;">{h(sup_names)}</td>'
                f'</tr>'
            )
        news_section = f"""
        <h2>Live News Alerts ({len(relevant)})</h2>
        <table>
          <tr>
            <th style="width:14%;text-align:center;">Severity</th>
            <th style="width:38%;">Headline</th>
            <th style="width:30%;">Summary</th>
            <th style="width:18%;">Affected Suppliers</th>
          </tr>
          {alert_rows}
        </table>
        """

    # ── AI analysis ───────────────────────────────────────────────────────
    ai_section = ""
    if analysis and analysis.get("narrative"):
        flags_li = "".join(
            f'<div class="flag-item">&#9654; {h(f)}</div>'
            for f in (analysis.get("flags") or [])
        )
        actions_li = "".join(
            f'<div class="action-item"><span class="action-num">{i+1}.</span>{h(a)}</div>'
            for i, a in enumerate(analysis.get("actions") or [])
        )
        ai_section = f"""
        <h2>AI Risk Analysis</h2>
        <div class="narrative">{h(analysis["narrative"])}</div>
        {"<h3>Key Observations</h3>" + flags_li if flags_li else ""}
        {"<h3>Recommended Actions</h3>" + actions_li if actions_li else ""}
        """

    # ── Assemble ───────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <style>{css}</style>
</head>
<body>
  {cover}
  {flags_html}
  {components_section}
  {geo_section}
  {suppliers_section}
  {news_section}
  {ai_section}
</body>
</html>"""
    return html


def generate_pdf(df, result: dict, news_articles: list, analysis: dict | None) -> bytes:
    """Render the risk report HTML and convert to PDF bytes via xhtml2pdf."""
    html = _build_html(df, result, news_articles, analysis)
    buf = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=buf)
    if pisa_status.err:
        raise RuntimeError(f"PDF generation failed: {pisa_status.err}")
    return buf.getvalue()
