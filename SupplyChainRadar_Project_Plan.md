# SupplyChainRadar — Project Plan

## The Pitch (One-Liner)

> **A free, no-signup tool that turns your supplier list into a live risk heatmap — combining structural risk analysis with real-time news intelligence to show you where your supply chain is vulnerable right now.**

---

## Why This Will Get Used (and Shared)

- **Post-COVID anxiety**: Every supply chain professional is thinking about risk and diversification
- **Live news integration**: Not just static analysis — the tool flags real disruptions happening RIGHT NOW near your suppliers. That's the "holy shit" moment that gets shared
- **Maps are inherently shareable**: A colorful heatmap of your supply chain with live alert pins is LinkedIn gold
- **No good free tool exists**: Enterprise solutions (Resilinc, Everstream) cost $50K+/year — there's nothing for SMBs, analysts, or students
- **The viral loop**: User runs their data → sees a live news alert about their supplier region → screenshots it → posts on LinkedIn → tags colleagues → they try it

---

## Target Users

| Persona | Why They Care |
|---------|---------------|
| Supply Chain Analyst | Needs to present risk to leadership — this gives them a ready-made visual |
| Procurement Manager | Wants to know: "am I too dependent on one region/supplier?" |
| Operations Manager | Needs to flag risks before they become disruptions |
| IE/Supply Chain Students | Portfolio projects, homework, learning |
| Consultants | Quick diagnostic tool for client engagements |

---

## Feature Breakdown

### Phase 1 — MVP Core (Weeks 1–3)

**Data Input**
- Manual form: add suppliers one by one (name, country/city, category, lead time in days, % of spend)
- CSV upload: drag-and-drop a CSV file with supplier data
- Demo mode: pre-loaded sample dataset so visitors can explore instantly without uploading anything

**Interactive Map**
- World map with supplier markers (use Folium/Leaflet)
- Color-coded by risk level (green → yellow → orange → red)
- Click a marker → see supplier details popup
- Cluster markers when zoomed out

**Risk Scoring Engine (the IE showcase)**
- **Geographic Concentration Risk (HHI)**: Herfindahl-Hirschman Index by country/region — flags if too much spend is concentrated in one area
- **Single-Source Risk**: Flags categories where only 1 supplier exists (no backup)
- **Lead Time Risk**: Flags suppliers with lead times above a threshold (e.g., >45 days)
- **Spend Concentration (Pareto)**: Shows if 80% of spend goes to 20% of suppliers
- **Overall Risk Score**: Weighted composite score (0–100) with letter grade (A–F)

**Risk Dashboard**
- Overall score with gauge/dial visualization
- Breakdown cards for each risk dimension
- Top 3 risk flags highlighted prominently

### Phase 2 — Live News Intelligence (Weeks 4–5)

**News Scanning Engine**
- Use a news API (GNews API, NewsAPI, or Google News RSS feeds) to pull recent supply-chain-relevant news
- Keyword filters: port closure, strike, tariff, sanction, earthquake, flood, typhoon, factory fire, shortage, trade war, customs delay, embargo, bankruptcy, recall
- Filter by location: match news articles to countries/regions where the user's suppliers are located
- Scan frequency: on every dashboard load (cached for 1 hour to manage API limits)

**AI News Classifier (Claude API)**
- Feed raw news articles to Claude to classify:
  - Relevance score (0–10): How likely is this to disrupt supply chains?
  - Impact type: Logistics, Production, Regulatory, Natural Disaster, Geopolitical
  - Affected regions: Which countries/cities are impacted?
  - Severity: Low / Medium / High / Critical
  - Estimated duration: Short-term (<1 week), Medium (1–4 weeks), Long-term (>1 month)
- Filter out noise — only surface genuinely relevant disruptions

**Map Integration**
- Live alert pins on the map: pulsing red/orange markers for active disruption events
- Click an alert pin → see news headline, AI-generated impact summary, and which of YOUR suppliers are in the affected zone
- Alert banner at top of dashboard: "⚠️ 2 active disruptions detected near your suppliers"
- Visual distinction between structural risk (your data) and live risk (news events)

**News Feed Panel**
- Sidebar or collapsible panel showing latest relevant news items
- Each item shows: headline, source, date, severity badge, affected suppliers count
- AI-generated one-liner: "Port workers' strike in Rotterdam may delay shipments from 3 of your EU suppliers by 1–2 weeks"

**Supplier Impact Matching**
- Automatically cross-reference news locations with your supplier locations
- Proximity matching: flag suppliers within X km of a disruption event
- Direct impact vs. indirect impact (e.g., a port closure affects suppliers who ship through that port, not just those located there)

### Phase 3 — AI Analysis + What-If (Weeks 6–7)

**AI Risk Analysis Report**
- Feed supplier data + risk scores + live news context to Claude API
- Generate natural-language risk summary that combines structural AND live risks: "Your supply chain has a dangerous concentration in East Asia — 68% of spend flows through 3 suppliers in China and Vietnam. ADDITIONALLY, a typhoon warning in the South China Sea may disrupt shipping lanes this week..."
- Specific, actionable recommendations: "Consider qualifying a European or Latin American alternative for your Packaging category. In the short term, contact your Shenzhen suppliers about potential delays from the current port congestion."

**AI-Powered What-If Scenarios**
- "What happens if I lose Supplier X?" → recalculate scores instantly, show impact
- "What if lead times from China double?" → re-score with modified inputs
- News-triggered what-if: "Based on the current port strike, here's what your risk score looks like if lead times from this region increase by 2 weeks"

### Phase 4 — Polish & Virality (Weeks 8–9)

**Exportable Report (PDF)**
- One-click PDF download with map snapshot, risk scores, live alerts, and AI analysis
- Professional formatting — something you'd attach to an email to your VP
- Timestamped: "Supply Chain Risk Report — Generated March 16, 2026"

**Share Features**
- "Share your risk score" button → generates a shareable image/card optimized for LinkedIn
- Score badge: "My Supply Chain Risk Score: B+ (72/100) — 2 active alerts ⚠️ — Find yours at supplychainradar.com"

**Industry Benchmarks**
- Compare your scores against anonymized averages (seed with realistic benchmark data)
- "Your geographic concentration is worse than 65% of companies in your industry"

**Email/Webhook Alerts (Stretch)**
- Optional: enter your email and get notified when a new disruption is detected near your suppliers
- This creates a retention loop — users come back

### Phase 5 — Stretch Goals (Optional)

- Geopolitical risk overlay (flag suppliers in politically unstable regions — use a static dataset like Fragile States Index)
- Natural disaster risk layer (earthquake zones, flood plains, hurricane paths — static overlay)
- Historical disruption timeline (show past events like Suez Canal, COVID, chip shortage on a timeline)
- Multi-user: save and revisit your analysis (requires auth)
- Tier 2/3 supplier mapping (suppliers of your suppliers)

---

## Technical Architecture

### Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | **Flask** (Python) | Lightweight, you know Python, full control |
| Frontend | **Jinja2 templates + Tailwind CSS + Alpine.js** | Clean UI without React overhead |
| Map | **Folium** (generates Leaflet maps) or **Leaflet.js** directly | Free, interactive, beautiful maps |
| Charts | **Plotly** or **Chart.js** | Interactive dashboard visuals |
| AI | **Claude API** (Sonnet) | Risk narratives + news classification |
| News | **GNews API** (free tier: 100 req/day) or **NewsAPI** | Real-time supply chain news feed |
| Geocoding | **Geopy** (Nominatim) or **OpenCage** | Convert city/country → lat/lng |
| Caching | **Flask-Caching** (simple in-memory or file) | Cache news results (1hr) to stay within API limits |
| PDF Export | **WeasyPrint** or **ReportLab** | Professional PDF reports |
| Hosting | **Render** or **Railway** | Free tier, Python-friendly |
| Data | **JSON/CSV files** (no DB for MVP) | Keep it simple — no auth needed |

### Project Structure

```
supplychainradar/
├── app.py                  # Flask app — routes & logic
├── risk_engine.py          # Core risk scoring algorithms (HHI, Pareto, etc.)
├── news_engine.py          # News API integration + location matching
├── news_classifier.py      # Claude API: classify news relevance & severity
├── ai_analysis.py          # Claude API: risk narratives + recommendations
├── geocoder.py             # Location → coordinates conversion
├── pdf_generator.py        # PDF report creation
├── data/
│   ├── sample_data.csv     # Demo dataset
│   ├── benchmarks.json     # Industry benchmark data
│   └── disruption_keywords.json  # Supply chain disruption keyword list
├── templates/
│   ├── base.html           # Layout with Tailwind
│   ├── index.html          # Landing page + upload form
│   ├── dashboard.html      # Risk dashboard + map + news panel
│   └── report.html         # Full report view
├── static/
│   ├── css/
│   ├── js/
│   └── images/
├── tests/
│   ├── test_risk_engine.py
│   ├── test_news_engine.py
│   └── test_data/
├── requirements.txt
└── README.md
```

### Key Algorithms (risk_engine.py)

```
Geographic Concentration (HHI):
  - Group spend by country
  - HHI = Σ(share_i²) where share_i = country_spend / total_spend
  - HHI > 0.25 = High concentration (Red)
  - HHI 0.15–0.25 = Moderate (Yellow)
  - HHI < 0.15 = Diversified (Green)

Single-Source Risk:
  - For each category, count unique suppliers
  - If count == 1 → Critical risk flag
  - If count == 2 → Moderate risk flag

Lead Time Risk:
  - Score = % of spend with lead time > threshold (e.g., 45 days)
  - Weight by spend — a high-spend, long-lead supplier is worse

Spend Concentration (Gini/Pareto):
  - Calculate Gini coefficient across suppliers
  - Flag if top 20% of suppliers represent >80% of spend

Live News Risk Score:
  - Pull recent news (last 7 days) matching supplier countries/regions
  - Claude classifies each article: relevance (0–10), severity, impact type
  - Filter: only keep relevance ≥ 6
  - Match to suppliers by proximity (country match or city-level geo distance)
  - News risk score = weighted sum of (severity × affected_spend_%)
  - Decays over time: 7-day-old news counts less than today's

Overall Score:
  - Weighted average: Geo (25%) + Single-Source (20%) + Lead Time (20%) + Spend (15%) + Live News (20%)
  - Normalize to 0–100 scale
  - Letter grade: A (80+), B (60–79), C (40–59), D (20–39), F (<20)
  - If any live Critical-severity alert exists → score capped at C regardless of other factors
```

### News Intelligence Pipeline (news_engine.py + news_classifier.py)

```
Step 1: Collect
  - On dashboard load, call GNews/NewsAPI with supply chain keywords
  - Filter by user's supplier countries (e.g., "supply chain China", "port strike Germany")
  - Cache results for 1 hour (Flask-Caching)

Step 2: Classify (Claude API)
  - Batch articles (up to 10) into one Claude API call for cost efficiency
  - Prompt: "Classify each article for supply chain impact..."
  - Returns: relevance, severity, impact type, affected regions, estimated duration
  - Cost optimization: use Haiku for classification (fast + cheap), Sonnet for narratives

Step 3: Match
  - Cross-reference classified article regions with user's supplier locations
  - Country-level match (primary) + city/port proximity match (secondary)
  - Tag each supplier with relevant active alerts

Step 4: Display
  - Pulsing alert pins on map (distinct from supplier markers)
  - News feed panel with severity badges
  - AI-generated impact summary per alert
  - "X of your suppliers may be affected" count
```

---

## Week-by-Week Build Plan

### Week 1: Foundation + Risk Engine
- [ ] Set up Flask project structure, virtual environment, Git repo
- [ ] Build `risk_engine.py` with all 4 structural risk calculations + unit tests
- [ ] Create CSV parser (handle messy data, missing fields)
- [ ] Build sample dataset (20–30 realistic suppliers across industries)
- [ ] Simple landing page with file upload form

### Week 2: Map + Dashboard
- [ ] Integrate geocoding (country/city → lat/lng)
- [ ] Build interactive Folium/Leaflet map with color-coded markers
- [ ] Create dashboard layout: risk gauge, breakdown cards, top flags
- [ ] Wire up CSV upload → risk engine → dashboard pipeline
- [ ] Add manual entry form (add suppliers one by one)

### Week 3: MVP Polish
- [ ] Demo mode with pre-loaded sample data
- [ ] Responsive design (mobile-friendly)
- [ ] Error handling (bad CSV, missing fields, invalid data)
- [ ] Loading states and smooth transitions
- [ ] Deploy to Render/Railway — get a live URL

### Week 4: Live News Intelligence — Backend
- [ ] Set up GNews API (or NewsAPI) integration in `news_engine.py`
- [ ] Build supply chain disruption keyword list (`disruption_keywords.json`)
- [ ] Build news fetcher: pull articles filtered by supplier countries + keywords
- [ ] Implement Flask-Caching (1-hour TTL) to stay within API rate limits
- [ ] Build `news_classifier.py`: Claude API (Haiku) to classify relevance, severity, impact type
- [ ] Build supplier-to-news matching logic (country match + proximity)
- [ ] Unit tests with mock news data

### Week 5: Live News Intelligence — Frontend + Map
- [ ] Add pulsing alert pins on the map for active disruption events
- [ ] Build news feed sidebar panel (headline, source, severity badge, affected suppliers)
- [ ] Alert banner at top of dashboard: "⚠️ X active disruptions near your suppliers"
- [ ] Click alert pin → popup with AI-generated impact summary
- [ ] Integrate live news risk score into overall risk scoring
- [ ] Test with real news data — verify relevance filtering quality

### Week 6: AI Analysis + What-If
- [ ] Integrate Claude API (Sonnet) for full risk narrative generation
- [ ] Combine structural risk + live news context in AI prompt
- [ ] "What-if" scenario engine (remove supplier, change lead times)
- [ ] Interactive what-if UI (dropdown: "What if I lose [Supplier X]?")
- [ ] News-triggered what-if: auto-suggest scenarios based on active alerts
- [ ] Side-by-side comparison view (before vs. after)
- [ ] Cache AI responses to manage API costs

### Week 7: PDF Export + Shareability
- [ ] Generate professional PDF report (map, scores, live alerts, AI analysis)
- [ ] Timestamp the report: "Risk snapshot as of [date/time]"
- [ ] "Share your score" card generator (image for LinkedIn)
- [ ] Meta tags for link previews (Open Graph)
- [ ] Industry benchmark comparison visuals

### Week 8: Final Polish + Launch Prep
- [ ] Performance optimization (lazy load map, async news fetch)
- [ ] Cross-browser testing
- [ ] Write README with screenshots + architecture diagram for GitHub
- [ ] Record demo GIF/video showing live alerts in action
- [ ] Prepare LinkedIn launch post
- [ ] Add to CV + update portfolio

---

## LinkedIn Launch Strategy

**Post Template:**
> I built a free tool that monitors your supply chain risk in real-time — using live news + data analysis.
>
> Upload your supplier list and instantly get:
> 🗺️ Interactive risk heatmap with live disruption alerts
> 📡 Real-time news scanning — port strikes, natural disasters, sanctions — matched to YOUR suppliers
> 📊 Quantitative risk scoring (HHI, Pareto, single-source analysis)
> 🤖 AI-generated risk report with specific recommendations
>
> Enterprise tools charge $50K+/year for this. This one is free. No signup.
>
> Try it: [link]
>
> I built this as an IE student at TAU who spent 4 years managing operations. Supply chain visibility shouldn't be locked behind enterprise contracts.
>
> #SupplyChain #Operations #IndustrialEngineering #RiskManagement

**Engagement triggers:**
- Tag relevant people (professors, supply chain influencers)
- Post on a Tuesday or Wednesday morning (peak LinkedIn engagement)
- Reply to every comment within 1 hour
- Follow up with a "lessons learned" post 1 week later

---

## How This Looks on Your CV

```
SupplyChainRadar — Real-Time Supply Chain Risk Intelligence Tool
2025 – Present
- Built and deployed a full-stack web application that combines supplier
  data analysis with live news intelligence to generate interactive risk
  heatmaps and AI-powered disruption alerts.
- Implemented quantitative risk scoring (HHI, Gini coefficient, Pareto
  analysis) to flag geographic concentration, single-source dependencies,
  and lead time vulnerabilities.
- Built a real-time news intelligence pipeline: API-driven news scanning,
  AI classification (relevance, severity, impact type), and automatic
  supplier-to-disruption matching.
- Integrated Claude API for natural-language risk narratives, actionable
  recommendations, and what-if scenario analysis.
- Tech stack: Python, Flask, Leaflet.js, Plotly, Claude API, GNews API,
  Tailwind CSS, Render.
- Live at supplychainradar.com
```

---

## Interview Talking Points

- **"Walk me through the risk scoring"** → Explain HHI, Gini, why you weighted dimensions the way you did, how live news risk integrates with structural risk, tradeoffs
- **"How does the news intelligence work?"** → News API → keyword filtering → Claude classifies relevance/severity → geo-match to suppliers → alert pins on map. Explain the caching strategy and cost optimization (Haiku for classification, Sonnet for narratives)
- **"How would you improve it?"** → Real-time data feeds (AIS shipping data), multi-tier visibility (tier 2/3 suppliers), Monte Carlo simulation for probabilistic risk, user accounts + historical tracking
- **"Tell me about a technical challenge"** → News relevance filtering (90% of articles are noise — how to classify accurately), geocoding edge cases, handling messy CSV data, prompt engineering for consistent AI output, staying within free API tier limits
- **"What did you learn?"** → How to quantify qualitative risk, the gap between enterprise tools and what SMBs need, building for real users vs. building for a grade, how to combine static analysis with real-time data streams

---

## API Cost Budget (Keeping It Under $5/month)

| Service | Free Tier | Cost Strategy |
|---------|-----------|---------------|
| **GNews API** | 100 requests/day | Cache aggressively (1hr TTL). ~24 unique fetches/day max |
| **Claude Haiku** (news classification) | Pay per token | Batch 10 articles per call. ~$0.01 per batch |
| **Claude Sonnet** (risk narratives) | Pay per token | 1 call per dashboard load, cached. ~$0.03 per call |
| **Geopy/Nominatim** | Free (rate limited) | Cache geocoding results permanently — locations don't change |
| **Render** (hosting) | Free tier | Sufficient for MVP traffic |

**Total estimated cost: $2–5/month** (similar to your JobMatcher architecture)

---

## News API Comparison

| API | Free Tier | Pros | Cons |
|-----|-----------|------|------|
| **GNews API** | 100 req/day | Simple, good coverage, fast | Limited filtering |
| **NewsAPI** | 100 req/day (dev only) | Great filtering, many sources | Free tier = dev only, no production |
| **Google News RSS** | Unlimited | Free forever, no key needed | Raw RSS, need to parse yourself, less structured |
| **Bing News Search** | 1000 req/month | Good relevance | Microsoft Azure setup overhead |

**Recommendation:** Start with **GNews API** for development. If you hit limits in production, switch to **Google News RSS** (unlimited, free) + your own parsing layer.
