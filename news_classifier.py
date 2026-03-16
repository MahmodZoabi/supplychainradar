"""
news_classifier.py — Classify supply-chain news articles using Claude Haiku.

Pipeline:
    classify_articles(articles) → classified list (relevance < 6 filtered out)

Each article gains:
    relevance_score    int  0–10
    severity           str  Low | Medium | High | Critical
    impact_type        str  e.g. "Port Closure", "Natural Disaster", …
    affected_regions   list[str]
    estimated_duration str  e.g. "1–2 weeks"
    summary            str  one sentence
"""

import json
import os

import anthropic

_MODEL = "claude-haiku-4-5-20251001"
_BATCH_SIZE = 10
_MIN_RELEVANCE = 6

_SYSTEM = (
    "You are a supply-chain risk analyst. "
    "Given a list of news article titles and descriptions, classify each one. "
    "Return ONLY a JSON array with one object per article, in the same order. "
    "Each object must have exactly these keys: "
    "relevance_score (int 0-10, how relevant to supply-chain disruption), "
    "severity (one of: Low, Medium, High, Critical), "
    "impact_type (short label, e.g. 'Port Closure', 'Trade Restriction', "
    "'Natural Disaster', 'Labour Strike', 'Geopolitical Tension', 'Logistics Delay', 'Other'), "
    "affected_regions (list of strings — country or region names mentioned), "
    "estimated_duration (short string, e.g. '1-2 weeks', '1-3 months', 'Ongoing', 'Unknown'), "
    "summary (one sentence describing the supply-chain impact). "
    "Return valid JSON only — no markdown, no commentary."
)


def _build_user_message(batch: list[dict]) -> str:
    lines = []
    for i, a in enumerate(batch, 1):
        title = a.get("title", "").strip()
        desc = (a.get("description") or a.get("content") or "").strip()[:300]
        lines.append(f"{i}. Title: {title}\n   Description: {desc}")
    return "Classify these articles:\n\n" + "\n\n".join(lines)


def _call_claude(batch: list[dict], client: anthropic.Anthropic) -> list[dict]:
    """Send one batch to Claude; return list of classification dicts."""
    msg = client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _build_user_message(batch)}],
    )
    raw = msg.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def classify_articles(articles: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Classify *articles* with Claude Haiku in batches of up to 10.

    Returns
    -------
    (classified, missing_keys)
        classified   – articles with relevance >= 6, enriched with classification fields
        missing_keys – list of missing env-var names (for UI warnings)
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        # No key — return articles unclassified with a default classification
        fallback = []
        for a in articles:
            enriched = dict(a)
            enriched.setdefault("relevance_score", 7)
            enriched.setdefault("severity", "Medium")
            enriched.setdefault("impact_type", "Unknown")
            enriched.setdefault("affected_regions", a.get("_query_countries", []))
            enriched.setdefault("estimated_duration", "Unknown")
            enriched.setdefault("summary", a.get("description", a.get("title", ""))[:200])
            fallback.append(enriched)
        return fallback, ["ANTHROPIC_API_KEY"]

    client = anthropic.Anthropic(api_key=api_key)
    classified: list[dict] = []

    for i in range(0, len(articles), _BATCH_SIZE):
        batch = articles[i : i + _BATCH_SIZE]
        try:
            classifications = _call_claude(batch, client)
        except Exception:
            # If classification fails for a batch, keep articles with defaults
            classifications = [{}] * len(batch)

        for article, cls in zip(batch, classifications):
            enriched = dict(article)
            enriched["relevance_score"] = int(cls.get("relevance_score", 5))
            enriched["severity"] = cls.get("severity", "Medium")
            enriched["impact_type"] = cls.get("impact_type", "Other")
            enriched["affected_regions"] = cls.get(
                "affected_regions", article.get("_query_countries", [])
            )
            enriched["estimated_duration"] = cls.get("estimated_duration", "Unknown")
            enriched["summary"] = cls.get(
                "summary", article.get("description", article.get("title", ""))[:200]
            )
            if enriched["relevance_score"] >= _MIN_RELEVANCE:
                classified.append(enriched)

    return classified, []
