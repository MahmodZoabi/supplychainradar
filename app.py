"""
app.py — Flask application for SupplyChainRadar

Routes:
    GET  /          Landing page with CSV upload form
    POST /analyze   Parse uploaded CSV and return risk analysis as JSON
    GET  /demo      Run risk engine on the bundled sample dataset
"""

import io
import os

import pandas as pd
from flask import Flask, jsonify, render_template, request

from risk_engine import calculate_overall_risk

app = Flask(__name__)

REQUIRED_COLUMNS = {"name", "country", "category", "lead_time_days", "spend_pct"}
SAMPLE_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_data.csv")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_and_validate(file_stream) -> tuple[pd.DataFrame | None, str | None]:
    """Read CSV from a file-like object and validate required columns."""
    try:
        df = pd.read_csv(file_stream)
    except Exception as exc:
        return None, f"Could not parse CSV: {exc}"

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        return None, f"Missing required columns: {', '.join(sorted(missing))}"

    # Coerce numeric columns; drop rows where coercion fails
    for col in ("lead_time_days", "spend_pct"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    bad_rows = df[["lead_time_days", "spend_pct"]].isna().any(axis=1).sum()
    df = df.dropna(subset=["lead_time_days", "spend_pct"])

    if df.empty:
        return None, "No valid rows found after parsing numeric columns."

    result = calculate_overall_risk(df)
    if bad_rows:
        result["warnings"] = [f"{bad_rows} row(s) skipped due to non-numeric values."]

    return result, None


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
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only CSV files are accepted."}), 400

    result, error = _parse_and_validate(io.TextIOWrapper(file.stream, encoding="utf-8"))
    if error:
        return jsonify({"error": error}), 400

    return jsonify(result)


@app.route("/demo")
def demo():
    try:
        df = pd.read_csv(SAMPLE_DATA_PATH)
    except FileNotFoundError:
        return jsonify({"error": "Sample data file not found."}), 500

    result = calculate_overall_risk(df)
    result["demo"] = True
    return jsonify(result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
