"""
ai_analysis.py — AI-generated risk narrative and recommendations using Claude Sonnet.

Entrypoint:
    generate_analysis(df, result, news_articles) -> dict | (None, missing_keys)

Returns a dict with:
    narrative   str   2-4 sentence combined structural + live risk overview
    flags       list  3-5 specific risk observations (bullet-point style)
    actions     list  3-5 concrete, prioritised recommendations
"""

import json
import os

import anthropic

_MODEL = "claude-sonnet-4-6"

_SYSTEM = (
    "You are a senior supply chain risk consultant. "
    "Analyse the supplied data and return ONLY a JSON object with three keys: "
    '"narrative" (string, 2-4 sentences summarising the most important combined risk), '
    '"flags" (list of 3-5 short strings, each one specific risk observation), '
    '"actions" (list of 3-5 short strings, each one concrete prioritised action). '
    "Be specific — mention supplier names, countries, percentages, and news events where relevant. "
    "Return valid JSON only. No markdown, no commentary."
)


def _build_prompt(df, result: dict, news_articles: list[dict]) -> str:
    total = result.get("total_spend_tracked_pct", 0)
    score = result.get("score", 0)
    grade = result.get("grade", "?")
    comp = result.get("components", {})

    # Top suppliers by spend
    top_sups = sorted(
        df.to_dict("records"), key=lambda r: float(r.get("spend_pct", 0)), reverse=True
    )[:6]
    sup_lines = "\n".join(
        f"  - {r['name']} ({r['country']}, {r['category']}, "
        f"lead={int(r['lead_time_days'])}d, spend={r['spend_pct']:.1f}%)"
        for r in top_sups
    )

    # Country concentration
    geo = comp.get("geographic", {})
    top_country = geo.get("top_country", "")
    top_pct = geo.get("top_country_share_pct", 0)

    # Single-source
    ss = comp.get("single_source", {})
    single_cats = [f["category"] for f in ss.get("flagged_categories", []) if f["risk"] == "Critical"]

    # Lead time
    lt = comp.get("lead_time", {})
    lt_flagged = [f["name"] for f in lt.get("flagged_suppliers", [])[:3]]

    # News context
    relevant_news = [a for a in news_articles if a.get("affected_suppliers")][:5]
    news_lines = ""
    if relevant_news:
        news_lines = "\n\nActive disruptions:\n" + "\n".join(
            f"  - [{a.get('severity','?')}] {a.get('title','')[:80]} "
            f"(affects {len(a.get('affected_suppliers',[]))} suppliers, "
            f"{a.get('affected_spend_pct',0)}% spend, est. {a.get('estimated_duration','?')})"
            for a in relevant_news
        )

    return f"""Supply chain risk data:

Overall: score {score:.1f}/100 (grade {grade}), {result.get('supplier_count',0)} suppliers, {total}% spend tracked

Risk components:
  - Geographic concentration (25%): {geo.get('level','?')} — top country {top_country} = {top_pct}%
  - Single-source risk (20%): {ss.get('level','?')} — {len(single_cats)} critical categories: {', '.join(single_cats) or 'none'}
  - Lead time risk (20%): {lt.get('level','?')} — {lt.get('flagged_spend_pct',0)}% of spend > 45 days
  - Spend concentration (15%): {comp.get('spend_concentration',{}).get('level','?')} — Gini {comp.get('spend_concentration',{}).get('gini',0):.2f}
  - Live news risk (20%): {comp.get('news',{}).get('level','?')}

Top suppliers by spend:
{sup_lines}{news_lines}

Top risk flags already identified:
{chr(10).join('  - ' + f for f in result.get('top_flags', []))}

Generate the analysis JSON now."""


def generate_analysis(
    df, result: dict, news_articles: list[dict]
) -> tuple[dict | None, list[str]]:
    """
    Returns (analysis_dict, missing_keys).
    analysis_dict is None if the API key is missing.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None, ["ANTHROPIC_API_KEY"]

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(df, result, news_articles)

    msg = client.messages.create(
        model=_MODEL,
        max_tokens=1200,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    if msg.stop_reason == "max_tokens":
        # Response was truncated — return a safe fallback rather than crash
        return {
            "narrative": "Analysis could not be completed (response too long). Try reducing the number of suppliers or news articles.",
            "flags": [],
            "actions": [],
        }, []

    raw = msg.content[0].text.strip()
    # Strip markdown code fences if the model wrapped the JSON
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "narrative": f"Analysis returned malformed JSON ({exc}). Raw response saved for debugging.",
            "flags": [],
            "actions": [],
        }, []

    return data, []
