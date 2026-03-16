"""
app.py — Flask application for SupplyChainRadar

Routes:
    GET  /               Landing page with CSV upload form
    POST /analyze        Parse uploaded CSV → JSON risk result + stores suppliers in session
    GET  /demo           Run risk engine on sample data → JSON (for landing page inline)
    GET  /dashboard      Full dashboard: map, scores, supplier table, add-supplier form
    GET  /dashboard/demo Full dashboard pre-loaded with sample data
    POST /supplier/add   Append a single supplier row, redirect back to dashboard
    GET  /supplier/reset Clear session suppliers → redirect to dashboard (sample data)
"""

import io
import os
import time

import folium
import pandas as pd
from branca.element import Element as BrancaElement
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_caching import Cache
from folium.plugins import MarkerCluster

from geocoder import geocode_dataframe
from news_classifier import classify_articles
from news_engine import compute_news_risk_score, fetch_news, match_news_to_suppliers
from risk_engine import calculate_overall_risk, get_supplier_risk_levels

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-supplychainradar-2026")
app.config["CACHE_TYPE"] = "SimpleCache"
app.config["CACHE_DEFAULT_TIMEOUT"] = 3600  # 1 hour
cache = Cache(app)

REQUIRED_COLUMNS = {"name", "country", "category", "lead_time_days", "spend_pct"}
SAMPLE_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_data.csv")
MAP_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "static", "map_current.html")

GRADE_COLORS = {
    "A": "#22c55e",
    "B": "#14b8a6",
    "C": "#eab308",
    "D": "#f97316",
    "F": "#ef4444",
}

_RISK_HEX = {
    "red":    "#ef4444",
    "orange": "#f97316",
    "yellow": "#eab308",
    "green":  "#22c55e",
}
_RISK_LABEL = {
    "red": "High Risk", "orange": "Elevated", "yellow": "Moderate", "green": "Low Risk"
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_suppliers_df() -> pd.DataFrame:
    """Current session suppliers, or the bundled sample dataset."""
    if session.get("suppliers"):
        return pd.DataFrame(session["suppliers"])
    return pd.read_csv(SAMPLE_DATA_PATH)


def _news_cache_key(df: pd.DataFrame) -> str:
    countries = sorted(df["country"].dropna().unique().tolist())
    return "news_" + "_".join(countries)


def _run_news_pipeline(df: pd.DataFrame) -> dict:
    """Run the full fetch→classify→match pipeline; cache for 1 hour."""
    key = _news_cache_key(df)
    cached = cache.get(key)
    if cached is not None:
        return cached

    countries = df["country"].dropna().unique().tolist()
    missing_keys: list[str] = []

    raw_articles, mk1 = fetch_news(countries)
    missing_keys.extend(mk1)
    classified, mk2 = classify_articles(raw_articles)
    missing_keys.extend(mk2)
    articles = match_news_to_suppliers(classified, df)
    news_risk_score = compute_news_risk_score(articles)

    payload = {
        "articles": articles,
        "missing_api_keys": missing_keys,
        "news_risk_score": round(news_risk_score, 4),
    }
    cache.set(key, payload)
    return payload


def _get_cached_news(df: pd.DataFrame) -> dict:
    """Return cached news payload if available; otherwise return empty payload instantly."""
    key = _news_cache_key(df)
    cached = cache.get(key)
    if cached is not None:
        return cached
    return {"articles": [], "missing_api_keys": [], "news_risk_score": 0.0}


_ALERT_SEV_COLOR = {
    "Critical": "#ef4444",
    "High":     "#f97316",
    "Medium":   "#eab308",
    "Low":      "#94a3b8",
}


def _build_map(df: pd.DataFrame, alert_articles: list[dict] | None = None) -> str:
    """
    Geocode df, assign per-supplier risk colours, build a Folium map, save to
    static/map_current.html, return a cache-busted URL.
    Pulsing alert pins are added for each item in alert_articles.
    """
    df_geo = geocode_dataframe(df)
    risk_levels = get_supplier_risk_levels(df)
    df_geo["risk_color"] = risk_levels

    m = folium.Map(
        location=[20, 0],
        zoom_start=2,
        tiles="CartoDB dark_matter",
        prefer_canvas=True,
    )

    cluster = MarkerCluster(
        options={"maxClusterRadius": 60, "showCoverageOnHover": False}
    ).add_to(m)

    for _, row in df_geo.iterrows():
        if pd.isna(row.get("lat")) or pd.isna(row.get("lon")):
            continue

        color = row.get("risk_color", "green")
        hex_c = _RISK_HEX[color]

        city_part = f"{row['city']}, " if str(row.get('city', '')).strip() else ""
        popup_html = f"""
        <div style="font-family:'Inter',sans-serif;min-width:190px;padding:2px 4px;">
          <div style="font-weight:700;font-size:14px;color:#0f172a;margin-bottom:5px;">
            {row['name']}
          </div>
          <div style="font-size:12px;color:#64748b;margin-bottom:8px;">
            {city_part}{row['country']}
          </div>
          <table style="width:100%;font-size:11px;border-collapse:collapse;">
            <tr>
              <td style="padding:3px 6px;background:#f8fafc;border-radius:4px 0 0 4px;">
                <div style="color:#94a3b8;margin-bottom:1px;">Category</div>
                <div style="font-weight:600;color:#1e293b;">{row['category']}</div>
              </td>
              <td style="padding:3px 6px;background:#f8fafc;border-radius:0 4px 4px 0;">
                <div style="color:#94a3b8;margin-bottom:1px;">Lead Time</div>
                <div style="font-weight:600;color:#1e293b;">{int(row['lead_time_days'])} days</div>
              </td>
            </tr>
            <tr><td colspan="2" style="height:4px;"></td></tr>
            <tr>
              <td style="padding:3px 6px;background:#f8fafc;border-radius:4px 0 0 4px;">
                <div style="color:#94a3b8;margin-bottom:1px;">Spend</div>
                <div style="font-weight:600;color:#1e293b;">{row['spend_pct']:.1f}%</div>
              </td>
              <td style="padding:3px 6px;border-radius:0 4px 4px 0;"
                  style="background:#fee2e2;">
                <div style="color:#94a3b8;margin-bottom:1px;">Risk</div>
                <div style="font-weight:600;color:{hex_c};">{_RISK_LABEL[color]}</div>
              </td>
            </tr>
          </table>
        </div>
        """

        dot_html = (
            f'<div style="background:{hex_c};width:14px;height:14px;border-radius:50%;'
            f'border:2px solid rgba(255,255,255,0.9);'
            f'box-shadow:0 0 8px rgba(0,0,0,0.5);"></div>'
        )

        folium.Marker(
            location=[row["lat"], row["lon"]],
            popup=folium.Popup(popup_html, max_width=220),
            tooltip=f"{row['name']} — {_RISK_LABEL[color]}",
            icon=folium.DivIcon(html=dot_html, icon_size=(14, 14), icon_anchor=(7, 7)),
        ).add_to(cluster)

    # --- Alert pins for live disruption events ---
    if alert_articles:
        # Inject pulsing keyframe CSS into the Folium map HTML
        pulse_css = BrancaElement(
            "<style>"
            "@keyframes scr-pulse{"
            "0%{box-shadow:0 0 0 0 rgba(239,68,68,.7);}"
            "70%{box-shadow:0 0 0 12px rgba(239,68,68,0);}"
            "100%{box-shadow:0 0 0 0 rgba(239,68,68,0);}}"
            ".alert-pin{animation:scr-pulse 1.8s ease-out infinite;border-radius:50%;}"
            "</style>"
        )
        m.get_root().html.add_child(pulse_css)

        for article in alert_articles:
            affected = article.get("affected_suppliers", [])
            if not affected:
                continue
            names = {s["name"] for s in affected}
            sub = df_geo[df_geo["name"].isin(names)].dropna(subset=["lat", "lon"])
            if sub.empty:
                continue
            lat = float(sub["lat"].mean())
            lon = float(sub["lon"].mean())
            severity = article.get("severity", "Medium")
            color = _ALERT_SEV_COLOR.get(severity, "#f97316")
            n_sup = len(affected)
            spend_pct = article.get("affected_spend_pct", 0)
            title_short = article.get("title", "")[:60]
            pin_html = (
                f'<div class="alert-pin" style="'
                f"width:16px;height:16px;background:{color};"
                f'border:2px solid rgba(255,255,255,.9);" '
                f'title="{title_short}"></div>'
            )
            popup_html = (
                f'<div style="font-family:Inter,sans-serif;min-width:210px;padding:4px;">'
                f'<div style="font-size:11px;font-weight:700;color:{color};'
                f'text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;">'
                f'⚠ {severity} Alert</div>'
                f'<div style="font-size:12px;font-weight:600;color:#0f172a;margin-bottom:6px;">'
                f'{article.get("title","")}</div>'
                f'<div style="font-size:11px;color:#475569;margin-bottom:6px;">'
                f'{article.get("summary","")}</div>'
                f'<div style="font-size:11px;color:#64748b;">'
                f'{n_sup} supplier{"s" if n_sup != 1 else ""} affected &middot; '
                f'{spend_pct}% of spend</div>'
                f'</div>'
            )
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=230),
                tooltip=f"⚠ {severity}: {article.get('title','')[:50]}",
                icon=folium.DivIcon(html=pin_html, icon_size=(16, 16), icon_anchor=(8, 8)),
            ).add_to(m)

    m.save(MAP_OUTPUT_PATH)
    return f"/static/map_current.html?t={int(time.time())}"


def _validate_and_parse_upload(file_stream) -> tuple[pd.DataFrame | None, str | None]:
    try:
        df = pd.read_csv(file_stream)
    except Exception as exc:
        return None, f"Could not parse CSV: {exc}"

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        return None, f"Missing required columns: {', '.join(sorted(missing))}"

    for col in ("lead_time_days", "spend_pct"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    bad = int(df[["lead_time_days", "spend_pct"]].isna().any(axis=1).sum())
    df = df.dropna(subset=["lead_time_days", "spend_pct"])

    if df.empty:
        return None, "No valid rows found after parsing numeric columns."

    return df, f"{bad} row(s) skipped due to non-numeric values." if bad else None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    if "file" not in request.files:
        return jsonify({"error": "No file field in request."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected."}), 400
    if not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only CSV files are accepted."}), 400

    df, warning = _validate_and_parse_upload(
        io.TextIOWrapper(file.stream, encoding="utf-8")
    )
    if df is None:
        return jsonify({"error": warning}), 400

    session["suppliers"] = df.to_dict("records")
    result = calculate_overall_risk(df)
    if warning:
        result["warnings"] = [warning]
    result["dashboard_url"] = url_for("dashboard")
    return jsonify(result)


@app.route("/demo")
def demo():
    df = pd.read_csv(SAMPLE_DATA_PATH)
    result = calculate_overall_risk(df)
    result["demo"] = True
    result["dashboard_url"] = url_for("dashboard") + "?demo=1"
    return jsonify(result)


@app.route("/dashboard")
def dashboard():
    if request.args.get("demo") == "1":
        session.pop("suppliers", None)

    df = _get_suppliers_df()
    is_demo = not bool(session.get("suppliers"))

    # Use cached news for map pins + score (no API calls on this path)
    news_payload = _get_cached_news(df)
    alert_articles = news_payload["articles"]
    news_risk_score = news_payload["news_risk_score"]
    has_critical = any(a.get("severity") == "Critical" for a in alert_articles)

    result = calculate_overall_risk(df, news_score=news_risk_score, has_critical_news=has_critical)
    map_url = _build_map(df, alert_articles=alert_articles)

    # Build supplier table rows with risk colours
    risk_levels = get_supplier_risk_levels(df)
    suppliers_table = []
    for i, (_, row) in enumerate(df.iterrows()):
        suppliers_table.append({
            "name": row["name"],
            "country": row["country"],
            "city": str(row.get("city", "") or ""),
            "category": row["category"],
            "lead_time_days": int(row["lead_time_days"]),
            "spend_pct": round(float(row["spend_pct"]), 1),
            "risk_color": risk_levels[i],
            "risk_label": _RISK_LABEL[risk_levels[i]],
        })

    # Sort: red first, then orange, yellow, green; ties broken by spend descending
    _order = {"red": 0, "orange": 1, "yellow": 2, "green": 3}
    suppliers_table.sort(key=lambda r: (_order[r["risk_color"]], -r["spend_pct"]))

    # Categories for datalist autocomplete
    categories = sorted(df["category"].unique().tolist())

    return render_template(
        "dashboard.html",
        result=result,
        map_url=map_url,
        suppliers=suppliers_table,
        grade_color=GRADE_COLORS.get(result["grade"], "#94a3b8"),
        is_demo=is_demo,
        categories=categories,
        error=request.args.get("error"),
        alert_count=len([a for a in alert_articles if a.get("affected_suppliers")]),
    )


@app.route("/supplier/add", methods=["POST"])
def supplier_add():
    df = _get_suppliers_df()

    name = request.form.get("name", "").strip()
    country = request.form.get("country", "").strip()
    city = request.form.get("city", "").strip()
    category = request.form.get("category", "").strip()
    lead_raw = request.form.get("lead_time_days", "")
    spend_raw = request.form.get("spend_pct", "")

    errors = []
    if not name:
        errors.append("Supplier name is required.")
    if not country:
        errors.append("Country is required.")
    if not category:
        errors.append("Category is required.")

    try:
        lead_time = int(float(lead_raw))
        if lead_time <= 0:
            errors.append("Lead time must be a positive number.")
    except (ValueError, TypeError):
        errors.append("Lead time must be a number (days).")
        lead_time = 0

    try:
        spend_pct = round(float(spend_raw), 2)
        if spend_pct <= 0:
            errors.append("Spend % must be positive.")
    except (ValueError, TypeError):
        errors.append("Spend % must be a number.")
        spend_pct = 0.0

    if errors:
        return redirect(url_for("dashboard") + "?error=" + "; ".join(errors))

    new_row = {
        "name": name,
        "country": country,
        "city": city,
        "category": category,
        "lead_time_days": lead_time,
        "spend_pct": spend_pct,
    }
    new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    session["suppliers"] = new_df.to_dict("records")
    return redirect(url_for("dashboard"))


@app.route("/supplier/reset")
def supplier_reset():
    session.pop("suppliers", None)
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# News API
# ---------------------------------------------------------------------------

@app.route("/api/news")
def api_news():
    """
    GET /api/news
    Runs the full news pipeline for the current supplier set.
    Cached for 1 hour (per-process SimpleCache).

    Response JSON:
        {
            "articles": [...],          # classified + supplier-matched
            "missing_api_keys": [...],  # e.g. ["GNEWS_API_KEY", "ANTHROPIC_API_KEY"]
            "news_risk_score": 0.0      # normalised 0-1
        }
    """
    df = _get_suppliers_df()
    return jsonify(_run_news_pipeline(df))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "development") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug)
