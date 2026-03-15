"""
geocoder.py — Location → (lat, lon) with persistent JSON cache.

Uses geopy Nominatim (free, rate-limited to 1 req/sec).
Cache lives at data/geocache.json so each city/country is only looked up once ever.
"""

import json
import os
import time

import pandas as pd
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim

CACHE_PATH = os.path.join(os.path.dirname(__file__), "data", "geocache.json")

# Module-level cache — loaded once per process, flushed to disk on write
_cache: dict | None = None


def _load_cache() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as fh:
            _cache = json.load(fh)
    else:
        _cache = {}
    return _cache


def _save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, indent=2)


def geocode_location(city: str | None, country: str) -> tuple[float, float] | None:
    """
    Return (lat, lon) for a city/country pair, or None if geocoding fails.

    Lookup order:
      1. Module-level cache (fast, no network)
      2. Nominatim with city+country
      3. Nominatim with country only (fallback)
    Results (including failures) are cached to disk so repeat calls are instant.
    """
    cache = _load_cache()

    city_str = city.strip() if city and str(city).strip() else ""
    query_full = f"{city_str}, {country}" if city_str else country
    key = query_full.lower()

    if key in cache:
        v = cache[key]
        return (float(v[0]), float(v[1])) if v else None

    geolocator = Nominatim(user_agent="supplychainradar/1.0 (contact: dev@supplychainradar.com)")
    queries = [query_full, country] if query_full != country else [country]

    for q in queries:
        try:
            time.sleep(1.1)  # Nominatim rate limit: max 1 req/sec
            loc = geolocator.geocode(q, timeout=10)
            if loc:
                coords = [loc.latitude, loc.longitude]
                cache[key] = coords
                _save_cache(cache)
                return (loc.latitude, loc.longitude)
        except (GeocoderTimedOut, GeocoderServiceError):
            continue

    # Cache the failure so we don't retry on every page load
    cache[key] = None
    _save_cache(cache)
    return None


def geocode_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'lat' and 'lon' columns to the DataFrame.
    Rows that cannot be geocoded receive NaN.
    City column is optional — falls back to country-only if absent or blank.
    """
    df = df.copy()
    lats: list[float | None] = []
    lons: list[float | None] = []

    for _, row in df.iterrows():
        city = str(row["city"]).strip() if "city" in df.columns and pd.notna(row.get("city")) else ""
        coords = geocode_location(city, row["country"])
        if coords:
            lats.append(coords[0])
            lons.append(coords[1])
        else:
            lats.append(None)
            lons.append(None)

    df["lat"] = lats
    df["lon"] = lons
    return df
