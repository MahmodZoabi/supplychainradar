"""
risk_engine.py — Core risk scoring algorithms for SupplyChainRadar

Scoring philosophy: each component returns a normalized risk level (0–1, higher = more risky).
The overall health score (0–100) inverts this so that higher = safer, letter grade A = best.

Without live news (Week 1), max composite risk = 0.80 → floor health score ≈ 20.
"""

import pandas as pd
import numpy as np
from typing import Any


# ---------------------------------------------------------------------------
# 1. Geographic Concentration (HHI)
# ---------------------------------------------------------------------------

def geographic_concentration_hhi(df: pd.DataFrame) -> dict[str, Any]:
    """
    Herfindahl-Hirschman Index across countries.

    HHI = Σ(share_i²) where share_i = country_spend / total_spend
    Thresholds (per spec):  >0.25 = High | 0.15–0.25 = Moderate | <0.15 = Low
    """
    total_spend = df["spend_pct"].sum()
    country_spend = df.groupby("country")["spend_pct"].sum()
    shares = country_spend / total_spend
    hhi = float((shares ** 2).sum())

    if hhi > 0.25:
        level, color = "High", "red"
    elif hhi >= 0.15:
        level, color = "Moderate", "yellow"
    else:
        level, color = "Low", "green"

    breakdown = {
        country: {
            "spend_pct": round(float(spend), 2),
            "share_pct": round(float(share) * 100, 1),
        }
        for country, spend, share in sorted(
            zip(country_spend.index, country_spend.values, shares.values),
            key=lambda x: x[1],
            reverse=True,
        )
    }

    top_country = str(country_spend.idxmax())
    top_share = round(float(shares.max()) * 100, 1)

    return {
        "score": round(hhi, 4),
        "level": level,
        "color": color,
        "breakdown": breakdown,
        "top_country": top_country,
        "top_country_share_pct": top_share,
        "country_count": len(country_spend),
    }


# ---------------------------------------------------------------------------
# 2. Single-Source Risk
# ---------------------------------------------------------------------------

def single_source_risk(df: pd.DataFrame) -> dict[str, Any]:
    """
    Flags categories with only 1 supplier (Critical) or 2 suppliers (Moderate).
    Risk score = fraction of total spend that is single-sourced.
    """
    total_spend = df["spend_pct"].sum()

    cat = (
        df.groupby("category")
        .agg(supplier_count=("name", "count"), total_spend=("spend_pct", "sum"))
        .reset_index()
    )

    critical_df = cat[cat["supplier_count"] == 1]
    moderate_df = cat[cat["supplier_count"] == 2]

    flagged = []
    for _, row in pd.concat([critical_df, moderate_df]).sort_values(
        "total_spend", ascending=False
    ).iterrows():
        risk_label = "Critical" if row["supplier_count"] == 1 else "Moderate"
        flagged.append(
            {
                "category": row["category"],
                "supplier_count": int(row["supplier_count"]),
                "spend_pct": round(float(row["total_spend"]), 1),
                "risk": risk_label,
            }
        )

    critical_spend = float(critical_df["total_spend"].sum()) if len(critical_df) else 0.0
    score = critical_spend / total_spend if total_spend > 0 else 0.0

    if len(critical_df) >= 3 or score > 0.30:
        level, color = "High", "red"
    elif len(critical_df) >= 1 or score > 0.10:
        level, color = "Moderate", "yellow"
    else:
        level, color = "Low", "green"

    return {
        "score": round(score, 4),
        "level": level,
        "color": color,
        "flagged_categories": flagged,
        "critical_count": len(critical_df),
        "moderate_count": len(moderate_df),
        "critical_spend_pct": round(critical_spend, 1),
    }


# ---------------------------------------------------------------------------
# 3. Lead Time Risk
# ---------------------------------------------------------------------------

def lead_time_risk(df: pd.DataFrame, threshold_days: int = 45) -> dict[str, Any]:
    """
    Spend-weighted risk from suppliers whose lead time exceeds the threshold.
    Score = risky_spend / total_spend (already 0–1).
    """
    total_spend = df["spend_pct"].sum()
    risky = df[df["lead_time_days"] > threshold_days].copy()
    risky_spend = float(risky["spend_pct"].sum())
    score = risky_spend / total_spend if total_spend > 0 else 0.0

    if score > 0.40:
        level, color = "High", "red"
    elif score > 0.20:
        level, color = "Moderate", "yellow"
    else:
        level, color = "Low", "green"

    flagged_suppliers = [
        {
            "name": row["name"],
            "country": row["country"],
            "category": row["category"],
            "lead_time_days": int(row["lead_time_days"]),
            "spend_pct": round(float(row["spend_pct"]), 1),
        }
        for _, row in risky.sort_values("spend_pct", ascending=False).iterrows()
    ]

    return {
        "score": round(score, 4),
        "level": level,
        "color": color,
        "threshold_days": threshold_days,
        "flagged_suppliers": flagged_suppliers,
        "flagged_spend_pct": round(risky_spend, 1),
        "avg_lead_time_days": round(float(df["lead_time_days"].mean()), 1),
        "max_lead_time_days": int(df["lead_time_days"].max()),
    }


# ---------------------------------------------------------------------------
# 4. Spend Concentration (Gini coefficient + Pareto check)
# ---------------------------------------------------------------------------

def spend_concentration_gini(df: pd.DataFrame) -> dict[str, Any]:
    """
    Gini coefficient for supplier spend distribution.
    Also flags if the top 20 % of suppliers hold ≥ 80 % of spend (Pareto 80/20).

    Gini thresholds (per spec): >0.60 = High | 0.40–0.60 = Moderate | <0.40 = Low
    """
    spends = df["spend_pct"].sort_values().values.astype(float)
    n = len(spends)
    total = spends.sum()

    if total == 0 or n == 0:
        return {"score": 0.0, "gini": 0.0, "level": "Low", "color": "green",
                "pareto_flag": False, "pareto_ratio": 0.0,
                "top_20pct_count": 0, "top_suppliers": []}

    # Standard discrete Gini formula (values sorted ascending, 1-indexed ranks)
    ranks = np.arange(1, n + 1)
    gini = float((2 * np.sum(ranks * spends)) / (n * total) - (n + 1) / n)
    gini = max(0.0, min(1.0, gini))

    # Pareto: do the top 20 % of suppliers (by count) hold ≥ 80 % of spend?
    top_n = max(1, int(np.ceil(n * 0.20)))
    top_spend = float(np.sort(spends)[-top_n:].sum())
    pareto_ratio = top_spend / total
    pareto_flag = bool(pareto_ratio >= 0.80)

    if gini > 0.60 or pareto_flag:
        level, color = "High", "red"
    elif gini > 0.40:
        level, color = "Moderate", "yellow"
    else:
        level, color = "Low", "green"

    top_suppliers = (
        df.nlargest(5, "spend_pct")[["name", "spend_pct", "country", "category"]]
        .assign(spend_pct=lambda d: d["spend_pct"].round(1))
        .to_dict("records")
    )

    return {
        "score": round(gini, 4),
        "gini": round(gini, 4),
        "level": level,
        "color": color,
        "pareto_flag": pareto_flag,
        "pareto_ratio_pct": round(pareto_ratio * 100, 1),
        "top_20pct_count": top_n,
        "top_suppliers": top_suppliers,
    }


# ---------------------------------------------------------------------------
# 5. Overall Risk Score
# ---------------------------------------------------------------------------

def calculate_overall_risk(
    df: pd.DataFrame, news_score: float = 0.0
) -> dict[str, Any]:
    """
    Weighted composite health score (0–100). Higher = safer / more resilient.

    Component weights (per spec):
        Geographic  25 %  |  Single-Source  20 %  |  Lead Time  20 %
        Spend       15 %  |  Live News      20 %  (0 until Phase 2)

    Without news (news_score=0), maximum possible risk contribution is 0.80,
    so health score floor is 20 (grade D). F requires the news component.

    Letter grades (resilience score):
        A ≥ 80  |  B 60–79  |  C 40–59  |  D 20–39  |  F < 20
    """
    geo = geographic_concentration_hhi(df)
    single = single_source_risk(df)
    lead = lead_time_risk(df)
    spend = spend_concentration_gini(df)

    # Normalize each component to 0–1 risk (1 = worst possible)
    geo_risk = min(1.0, geo["score"] / 0.25)          # HHI ≥ 0.25 → full risk
    single_risk = min(1.0, single["score"] / 0.50)     # ≥ 50 % single-sourced → full
    lead_risk = lead["score"]                           # already 0–1
    spend_risk = min(1.0, spend["gini"] / 0.70)        # Gini ≥ 0.70 → full risk
    news_risk = min(1.0, max(0.0, news_score))

    composite_risk = (
        geo_risk   * 0.25 +
        single_risk * 0.20 +
        lead_risk  * 0.20 +
        spend_risk * 0.15 +
        news_risk  * 0.20
    )

    health_score = round((1.0 - composite_risk) * 100, 1)
    health_score = max(0.0, min(100.0, health_score))

    if health_score >= 80:
        grade = "A"
    elif health_score >= 60:
        grade = "B"
    elif health_score >= 40:
        grade = "C"
    elif health_score >= 20:
        grade = "D"
    else:
        grade = "F"

    # Collect top risk flags for the dashboard
    flags: list[str] = []
    if geo["level"] == "High":
        flags.append(
            f"{geo['top_country_share_pct']}% of spend concentrated in {geo['top_country']}"
        )
    elif geo["level"] == "Moderate":
        flags.append(
            f"Moderate geographic concentration — top country: {geo['top_country']} ({geo['top_country_share_pct']}%)"
        )
    if single["critical_count"] > 0:
        n = single["critical_count"]
        flags.append(
            f"{n} single-sourced categor{'y' if n == 1 else 'ies'} "
            f"({single['critical_spend_pct']}% of spend with no backup supplier)"
        )
    if lead["level"] in ("High", "Moderate"):
        flags.append(
            f"{lead['flagged_spend_pct']}% of spend has lead time > {lead['threshold_days']} days"
        )
    if spend["pareto_flag"]:
        flags.append(
            f"Top {spend['top_20pct_count']} suppliers control {spend['pareto_ratio_pct']}% of spend"
        )

    return {
        "score": health_score,
        "grade": grade,
        "top_flags": flags[:3],
        "supplier_count": len(df),
        "total_spend_tracked_pct": round(float(df["spend_pct"].sum()), 1),
        "components": {
            "geographic": {
                "label": "Geographic Concentration",
                "weight_pct": 25,
                "risk_normalized": round(geo_risk, 4),
                **geo,
            },
            "single_source": {
                "label": "Single-Source Risk",
                "weight_pct": 20,
                "risk_normalized": round(single_risk, 4),
                **single,
            },
            "lead_time": {
                "label": "Lead Time Risk",
                "weight_pct": 20,
                "risk_normalized": round(lead_risk, 4),
                **lead,
            },
            "spend_concentration": {
                "label": "Spend Concentration",
                "weight_pct": 15,
                "risk_normalized": round(spend_risk, 4),
                **spend,
            },
            "news": {
                "label": "Live News Risk",
                "weight_pct": 20,
                "risk_normalized": round(news_risk, 4),
                "score": 0.0,
                "level": "N/A",
                "color": "gray",
                "available": news_risk > 0,
            },
        },
    }
