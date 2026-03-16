"""
news_engine.py — Supply-chain news fetching, filtering, and supplier matching.

Pipeline:
    1. fetch_news(countries)          → raw GNews articles (empty list if no API key)
    2. filter_by_recency(articles)    → drop articles older than N days
    3. _deduplicate(articles)         → remove near-duplicate titles
    4. match_news_to_suppliers(...)   → tag each article with affected suppliers

Callers are responsible for classification (news_classifier.py) between steps 3 and 4.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

import requests

GNEWS_BASE = "https://gnews.io/api/v4/search"
ARTICLE_MAX_AGE_DAYS = 7
_KEYWORDS_PATH = os.path.join(os.path.dirname(__file__), "data", "disruption_keywords.json")

# ---------------------------------------------------------------------------
# Keyword / region data
# ---------------------------------------------------------------------------

def _load_keywords() -> dict:
    with open(_KEYWORDS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _get_region_for_country(country: str, region_groups: dict) -> str:
    """Return the region that contains `country`, or the country itself."""
    for region, members in region_groups.items():
        if country in members:
            return region
    return country


def _group_countries_by_region(countries: list[str], region_groups: dict) -> dict[str, list[str]]:
    """
    Collapse a list of supplier countries into {region: [countries]} so we
    can issue one API call per region instead of one per country.
    """
    groups: dict[str, list[str]] = {}
    for c in countries:
        region = _get_region_for_country(c, region_groups)
        groups.setdefault(region, []).append(c)
    return groups


# ---------------------------------------------------------------------------
# Recency filter + deduplication
# ---------------------------------------------------------------------------

def filter_by_recency(articles: list[dict], max_age_days: int = ARTICLE_MAX_AGE_DAYS) -> list[dict]:
    """Drop articles published more than *max_age_days* ago."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    fresh = []
    for a in articles:
        pub = a.get("publishedAt", "")
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if dt >= cutoff:
                fresh.append(a)
        except (ValueError, AttributeError):
            fresh.append(a)  # keep if date is unparseable
    return fresh


def _deduplicate(articles: list[dict]) -> list[dict]:
    """
    Remove near-duplicate articles using title similarity (SequenceMatcher ≥ 0.80).
    Keeps the first occurrence of each near-duplicate cluster.
    """
    seen_titles: list[str] = []
    unique: list[dict] = []
    for a in articles:
        title = a.get("title", "").lower().strip()
        if not any(
            SequenceMatcher(None, title, s).ratio() >= 0.80 for s in seen_titles
        ):
            seen_titles.append(title)
            unique.append(a)
    return unique


# ---------------------------------------------------------------------------
# GNews API fetch
# ---------------------------------------------------------------------------

def _build_query(region: str, countries: list[str], primary_kws: list[str]) -> str:
    """
    Build a GNews-compatible boolean query:
        (<keyword_1> OR <keyword_2> ...) AND (<region> OR <country_1> OR ...)
    Capped to stay within GNews query-length limits.
    """
    kw_terms = " OR ".join(f'"{k}"' for k in primary_kws[:6])
    loc_terms = " OR ".join(f'"{t}"' for t in ([region] + countries[:3]))
    return f"({kw_terms}) AND ({loc_terms})"


def _fetch_gnews_page(query: str, api_key: str, max_results: int = 10) -> list[dict]:
    """Single GNews /search call. Raises on HTTP errors."""
    params = {
        "q": query,
        "lang": "en",
        "max": max_results,
        "token": api_key,
        "sortby": "publishedAt",
    }
    resp = requests.get(GNEWS_BASE, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("articles", [])


def fetch_news(supplier_countries: list[str]) -> tuple[list[dict], list[str]]:
    """
    Fetch supply-chain news for *supplier_countries*.

    Returns
    -------
    (articles, missing_keys)
        articles     – deduplicated, recency-filtered list of raw GNews article dicts
        missing_keys – list of env-var names that were absent (for UI warnings)
    """
    api_key = os.environ.get("GNEWS_API_KEY", "")
    if not api_key:
        return [], ["GNEWS_API_KEY"]

    kw_data = _load_keywords()
    region_groups = kw_data.get("region_groups", {})
    # Combine primary + logistics keywords as the disruption signal
    all_kws = kw_data.get("primary_keywords", []) + kw_data.get("logistics_keywords", [])

    region_map = _group_countries_by_region(supplier_countries, region_groups)

    raw: list[dict] = []
    for region, countries in region_map.items():
        query = _build_query(region, countries, all_kws)
        try:
            articles = _fetch_gnews_page(query, api_key)
            for a in articles:
                a["_query_region"] = region
                a["_query_countries"] = countries
            raw.extend(articles)
        except Exception:
            # One failing region doesn't abort the whole fetch
            continue

    articles = filter_by_recency(raw)
    articles = _deduplicate(articles)
    return articles, []


# ---------------------------------------------------------------------------
# Supplier matching
# ---------------------------------------------------------------------------

def _expand_regions(region_names: list[str], region_groups: dict) -> set[str]:
    """
    Given a list of strings that may be country or region names, return
    a flat set of lowercase country names.

    E.g. "East Asia" → {"china", "taiwan", "south korea", "japan"}
        "Germany"   → {"germany"}
    """
    expanded: set[str] = set()
    for name in region_names:
        name_lower = name.lower()
        # Check if it matches a region group key
        matched_region = False
        for region_key, members in region_groups.items():
            if name_lower == region_key.lower():
                expanded.update(m.lower() for m in members)
                matched_region = True
                break
        if not matched_region:
            expanded.add(name_lower)
    return expanded


def match_news_to_suppliers(
    classified_articles: list[dict],
    df,            # pd.DataFrame with at least ["name", "country", "spend_pct"]
) -> list[dict]:
    """
    For each article add:
        affected_suppliers  – list of {name, country, spend_pct} dicts
        affected_spend_pct  – % of total tracked spend in affected countries
    Matching is case-insensitive; region names are expanded to their member countries.
    """
    kw_data = _load_keywords()
    region_groups = kw_data.get("region_groups", {})
    total_spend = float(df["spend_pct"].sum()) or 1.0

    result = []
    for article in classified_articles:
        raw_regions: list[str] = article.get("affected_regions", [])
        affected_countries = _expand_regions(raw_regions, region_groups)

        matched_suppliers: list[dict] = []
        matched_spend = 0.0

        for _, row in df.iterrows():
            country_lower = row["country"].lower()
            # Direct country match OR supplier country contained in an affected region string
            is_match = country_lower in affected_countries or any(
                country_lower in r or r in country_lower for r in affected_countries
            )
            if is_match:
                matched_suppliers.append(
                    {
                        "name": row["name"],
                        "country": row["country"],
                        "category": row["category"],
                        "spend_pct": round(float(row["spend_pct"]), 1),
                    }
                )
                matched_spend += float(row["spend_pct"])

        enriched = dict(article)
        enriched["affected_suppliers"] = sorted(
            matched_suppliers, key=lambda s: s["spend_pct"], reverse=True
        )
        enriched["affected_spend_pct"] = round(matched_spend / total_spend * 100, 1)
        # Normalise source to a plain string for JSON serialisation
        src = enriched.get("source", "")
        if isinstance(src, dict):
            enriched["source"] = src.get("name", "")
        result.append(enriched)

    # Sort by severity then spend impact
    _severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    result.sort(
        key=lambda a: (
            _severity_order.get(a.get("severity", "Low"), 3),
            -a.get("affected_spend_pct", 0),
        )
    )
    return result
