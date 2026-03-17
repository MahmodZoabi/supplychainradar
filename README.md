# SupplyChainRadar

A free, no-signup tool that turns your supplier list into a live risk heatmap — combining quantitative risk scoring with real-time news intelligence.

**[Live Demo →](https://supplychainradar.onrender.com)**

---

## Features

- **Interactive risk map** — color-coded supplier markers (green → red) with pulsing live alert pins
- **Risk scoring engine** — weighted composite score (0–100, A–F) across five dimensions:
  - Geographic Concentration (HHI)
  - Single-Source Risk
  - Lead Time Risk
  - Spend Concentration (Gini/Pareto)
  - Live News Risk
- **Live news intelligence** — Google News RSS scanned per supplier region, matched to your specific suppliers
- **AI risk analysis** — Claude Sonnet generates a natural-language risk narrative with actionable recommendations
- **What-if scenarios** — instantly recalculate: "What if I lose Supplier X?" or "What if lead times double?"
- **Share your score** — one-click LinkedIn-ready snippet
- **Demo mode** — 23 pre-loaded suppliers across 13 countries, no upload needed

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask (Python) |
| Frontend | Tailwind CSS + Alpine.js |
| Map | Folium / Leaflet.js |
| AI | Claude API (Haiku + Sonnet) |
| News | Google News RSS |
| Geocoding | Geopy / Nominatim |
| Hosting | Render |

## Run Locally

```bash
git clone https://github.com/MahmodZoabi/supplychainradar.git
cd supplychainradar
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
flask run
```

Open [http://localhost:5000](http://localhost:5000). The app works without an Anthropic key — news still loads, AI panels are skipped.

## CSV Format

| Column | Description |
|--------|-------------|
| `name` | Supplier name |
| `country` | Country (English) |
| `city` | City (optional) |
| `category` | Product/service category |
| `lead_time_days` | Lead time in days |
| `spend_pct` | % of total spend (rows should sum to ~100) |

See [`data/sample_data.csv`](data/sample_data.csv) for an example.

## Keeping the App Awake (Render Free Tier)

Render spins down free services after 15 minutes of inactivity, causing slow cold starts. To prevent this, use [UptimeRobot](https://uptimerobot.com) (free) to ping the health endpoint every 14 minutes:

- **Monitor type:** HTTP(s)
- **URL:** `https://supplychainradar.onrender.com/health`
- **Interval:** 14 minutes

The `/health` endpoint returns `{"status": "ok"}` and is lightweight enough to keep the instance warm without affecting other users.

---

Built by [Mahmod Zoabi](https://github.com/MahmodZoabi) · MIT License
