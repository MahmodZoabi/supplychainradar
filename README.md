# SupplyChainRadar

**A free, no-signup tool that turns your supplier list into a live risk heatmap — combining quantitative risk analysis with real-time news intelligence.**

---

![SupplyChainRadar dashboard screenshot](docs/screenshot-placeholder.png)
> *Screenshot: Interactive risk dashboard with live news alerts and geographic heatmap*

---

## Features

- **Risk Scoring Engine** — Weighted composite score (0–100, A–F grade) built on four quantitative dimensions:
  - Geographic Concentration (HHI — Herfindahl-Hirschman Index)
  - Single-Source Risk (categories with only one supplier)
  - Lead Time Risk (suppliers above your configured threshold)
  - Spend Concentration (Pareto / Gini analysis)
- **Interactive Map** — Folium/Leaflet heatmap with color-coded supplier markers (green → red) and pulsing alert pins for live disruptions
- **Live News Intelligence** — Google News RSS scanned per supplier region, AI-classified by relevance and severity, matched to your specific suppliers
- **AI Risk Analysis** — Claude Sonnet generates a natural-language risk narrative combining structural risk with live disruption context, plus specific actionable recommendations
- **What-If Scenarios** — Instantly recalculate scores: "What if I lose Supplier X?" or "What if lead times from China double?"
- **Share Your Score** — One-click copy of a LinkedIn-ready risk score snippet
- **Demo Mode** — Pre-loaded with 23 realistic suppliers across 15 countries; no data upload required

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask (Python) |
| Frontend | Jinja2 + Tailwind CSS (CDN) + Alpine.js |
| Map | Folium (Leaflet.js) |
| AI | Claude API — Haiku for classification, Sonnet for narratives |
| News | Google News RSS (free, no key required) |
| Geocoding | Geopy / Nominatim with persistent local cache |
| Caching | Flask-Caching (SimpleCache, 1-hour TTL) |
| Hosting | Render |

---

## Running Locally

### 1. Clone and install

```bash
git clone https://github.com/MahmodZoabi/supplychainradar.git
cd supplychainradar
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
FLASK_SECRET_KEY=any-long-random-string
ANTHROPIC_API_KEY=sk-ant-...     # optional — enables AI classification + narratives
FLASK_DEBUG=true
```

The app works without an Anthropic key — news articles are still fetched and displayed, just without AI-powered classification and the narrative panel.

### 3. Run

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) — click **Try the Demo** to explore without uploading data.

---

## CSV Format

Upload a CSV with these columns:

| Column | Description | Example |
|--------|-------------|---------|
| `name` | Supplier name | `Foxconn` |
| `country` | Country (English name) | `Taiwan` |
| `city` | City (optional, improves geocoding) | `New Taipei City` |
| `category` | Product/service category | `Electronics Assembly` |
| `lead_time_days` | Lead time in days | `45` |
| `spend_pct` | % of total spend (all rows should sum to ~100) | `18.0` |

See [`data/sample_data.csv`](data/sample_data.csv) for a working example with 23 suppliers.

---

## Architecture

```
supplychainradar/
├── app.py               # Flask routes, session management, map building
├── risk_engine.py       # HHI, Gini, Pareto, single-source scoring + what-if
├── news_engine.py       # Google News RSS fetch, recency filter, deduplication,
│                        # supplier matching, news risk score
├── news_classifier.py   # Claude Haiku — batch article classification
├── ai_analysis.py       # Claude Sonnet — risk narrative + recommendations
├── geocoder.py          # Country/city → lat/lng with persistent JSON cache
├── data/
│   ├── sample_data.csv          # 23-supplier demo dataset
│   ├── disruption_keywords.json # Keyword lists + region groups for news matching
│   └── geocache.json            # Geocoding cache (gitignored, auto-built)
├── templates/
│   ├── index.html       # Landing page — CSV upload + demo mode
│   ├── dashboard.html   # Full dashboard — map, scores, news, AI, what-if
│   ├── 404.html
│   └── 500.html
├── static/
│   ├── favicon.svg
│   └── map_current.html # Generated Folium map (gitignored)
├── tests/
├── Procfile             # web: gunicorn app:app
└── requirements.txt
```

### News Pipeline

```
Google News RSS (free, no key)
    ↓  one query per supplier region, space-separated: "supply chain East Asia"
Filter by recency (7 days) + deduplicate (title similarity ≥ 0.80)
    ↓
Claude Haiku (batch 10 articles/call)
    → relevance score, severity, impact type, affected regions, summary
    → filter: relevance ≥ 6
    ↓
Supplier matching — expand region names → country sets, cross-reference with df
    → affected_suppliers list, affected_spend_pct
    ↓
News risk score = Σ (severity_weight/4 × affected_spend_pct/100 × time_decay)
    → feeds into overall health score (20% weight)
    → Critical alert → score capped at grade C (59.9)
```

### Risk Score Formula

```
Health Score (0–100) = 100 − weighted_risk

Components (risk_normalized 0–1 each):
  Geographic Concentration   25%  (HHI — high > 0.25)
  Single-Source Risk         20%  (categories with 1 supplier)
  Lead Time Risk             20%  (spend-weighted % above threshold)
  Spend Concentration        15%  (Gini coefficient)
  Live News Risk             20%  (time-decayed severity × spend impact)

Grade: A ≥ 80 · B ≥ 60 · C ≥ 40 · D ≥ 20 · F < 20
Critical news alert → cap at 59.9 (C) regardless of structural score
```

---

## Deployment (Render)

1. Push to GitHub
2. Create a new **Web Service** on [render.com](https://render.com)
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `gunicorn app:app` (or use the included `Procfile`)
5. Add environment variables in the Render dashboard (copy from `.env.example`)

The app reads `PORT` from the environment — Render sets this automatically.

---

## License

MIT — free to use, fork, and deploy.

---

*Built by [Mahmod Zoabi](https://github.com/MahmodZoabi) · [LinkedIn](https://www.linkedin.com/in/mahmod-zoabi/)*
