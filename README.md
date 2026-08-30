# HoshiyarLahore

### Heatwave Early Warning for Health Authorities

**Smart City Hackathon 2026 · Theme: City Intelligence**

**Live demo:** _add your deployed Vercel URL here once live (see `docs/DEPLOYMENT_GUIDE.md`)_

> *Hoshiyar* (ہوشیار) — "alert, watchful, prepared." An early-warning system that
> tells Lahore's health authorities where dangerous heat will hit first, and why.

Tehsil-level heat-risk intelligence for Lahore. HoshiyarLahore fuses live weather,
population, and land-cover data into an explainable heat-risk score for each of
Lahore's 5 administrative tehsils (2023 census) — so health authorities can
pre-position cooling centres, ORS supplies, and outreach teams in the right areas
*before* a heatwave arrives.

> **Test sentence:** When Punjab Health Department officials face a forecasted
> heatwave in Lahore, HoshiyarLahore tells them which specific towns will exceed
> dangerous heat thresholds, how many vulnerable people live in each, and why —
> so they can pre-position cooling centres, ORS supplies, and outreach teams in
> the right neighbourhoods 48–72 hours before the heat arrives.

---

## What's in this repository (Day 1 + Day 2 build)

This runs end-to-end today.

**Day 1 foundation:**
- ✅ 5 Lahore tehsils as a GeoJSON layer (with an OSM fetch script + fallback)
- ✅ Live weather integration with Open-Meteo (no API key required)
- ✅ SQLite database + schema + seed pipeline
- ✅ Interpretable heat-risk engine (Rothfusz heat index + weighted composite + attribution)
- ✅ FastAPI backend with `/api/towns`, `/api/towns/{id}`, `/api/alerts`, `/api/overview`
- ✅ Next.js + Leaflet dashboard (map, town detail panel, alerts, overview strip)
- ✅ A zero-setup `preview.html` you can open in a browser right now

**Day 2 additions:**
- ✅ Historical baseline pipeline — 10-year Open-Meteo archive fetcher + storage
- ✅ "X degrees above normal" comparison in each town's detail
- ✅ Town prioritisation ranking — the ordered "deploy resources here first" list
- ✅ New `/api/ranking` endpoint + historical block on `/api/towns/{id}`
- ✅ Dashboard: Alerts / Priority-ranking tabs + "Compared to normal" card
- ✅ Offline mock seeders for both weather and historical baselines

**Day 3 additions:**
- ✅ 72-hour forecast heat-risk — every hour scored with the same interpretable engine
- ✅ Predictive lead-time alerts — "Lahore City expected to reach Critical in ~13h"
- ✅ New `/api/towns/{id}/forecast` + `/api/predictive-alerts` endpoints
- ✅ Dashboard: forecast timeline (daily peaks + hourly bars) in the town panel
- ✅ Dashboard: "Forecast" tab with predictive lead-time warnings

**Day 4 additions:**
- ✅ Data validation script (`validate_data.py`) — pre-submission safety check
- ✅ Loading + error states (actionable full-screen error when backend is down)
- ✅ Mobile-responsive layout, verified at phone width
- ✅ Weight validation documented (model differentiates by density + vegetation)
- ✅ Timed ≤3-minute demo script (`docs/DEMO_SCRIPT.md`)

**Pre-deployment additions:**
- ✅ Cooling-centre locations — toggleable map layer of hospitals, parks, venues
  (`/api/cooling-centres`), completing the "where to deploy" decision loop
- ✅ Situation reports — copy-paste operational brief + SMS per tehsil
  (`/api/towns/{id}/sitrep`), assembled from risk + forecast + exposure + action
- ✅ **Auto-refresh** — a background scheduler inside the backend keeps weather
  (hourly) and historical baselines (daily) current automatically, no manual
  script-running needed. `GET /api/status` reports freshness honestly (including
  when a refresh fails); `POST /api/refresh` forces an immediate update. See
  `docs/AUTO_REFRESH.md`. Requires a persistent backend process (Render/Railway
  Web Service) — will not auto-refresh on serverless hosting.
- ✅ Next.js production build verified; 25 passing tests
- ✅ **What-if scenario simulator** — drag temperature/humidity sliders in the
  town panel and watch the risk score, gauge, and attribution update live,
  computed client-side (`frontend/src/lib/riskEngine.js`, a verified JS port
  of the backend risk engine — matches exactly in ~80% of cases, never differs
  by more than 0.1/100, risk band always correct)
- ✅ **Visual redesign** — moved from generic dark-dashboard styling to a warm
  "instrument panel" identity: Space Grotesk + IBM Plex Sans + IBM Plex Mono
  type system, a radial gauge dial as the signature risk-score display, and a
  bronze/ember accent palette distinct from the risk-band colors. Fonts load
  via a runtime `<link>` tag (not build-time fetch) so the build never depends
  on network access.

Later days add: real boundaries + live data, deployment, demo video, pitch deck
(see `docs/BUILD_PLAN.md`).

---

## Quick start

### Option A — Instant preview (no setup)

Open **`preview.html`** in any modern browser. It shows the full dashboard using
a snapshot of mock data. (The interactive map needs internet to load tiles; the
risk data, alerts, and detail panel work offline.)

### Option B — Run the real stack

**1. Backend**

```bash
cd hoshiyar-lahore
python -m pip install -r backend/requirements.txt

# Initialise DB and load towns
python -m backend.app.db.database

# Get weather. EITHER real (needs internet, no API key):
python backend/scripts/refresh_weather.py
# OR mock (works offline, clearly flagged as mock):
python backend/scripts/seed_mock_weather.py

# Day 2: historical baselines. EITHER real (needs internet, slow ~minutes):
python backend/scripts/refresh_historical.py
# OR mock (works offline, flagged with years_used=0):
python backend/scripts/seed_mock_historical.py

# Start the API - this ALSO starts the auto-refresh scheduler, which keeps
# weather (hourly) and historical baselines (daily) current automatically
# from here on. See docs/AUTO_REFRESH.md.
uvicorn backend.app.main:app --reload --port 8000
```

Visit http://localhost:8000/docs for interactive API docs.

**2. Frontend**

```bash
cd frontend
npm install
# point the frontend at your backend (defaults to localhost:8000)
echo "NEXT_PUBLIC_API_BASE=http://localhost:8000" > .env.local
npm run dev
```

Visit http://localhost:3000.

### Optional — Fetch real town boundaries from OpenStreetMap

```bash
python backend/scripts/fetch_boundaries.py
```

This overwrites `data/geojson/lahore_towns.geojson` with real OSM admin
boundaries where available, falling back to approximate polygons otherwise.
**Verify the output on https://geojson.io before relying on it.**

---

## Repository structure

```
hoshiyar-lahore/
├── README.md
├── preview.html                 # zero-setup dashboard preview
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py              # FastAPI app + endpoints
│   │   ├── db/
│   │   │   ├── schema.sql       # SQLite schema
│   │   │   └── database.py      # DB helpers + town seeding
│   │   └── services/
│   │       ├── open_meteo.py         # Open-Meteo client (weather + archive)
│   │       ├── heat_index.py         # Rothfusz heat index
│   │       ├── risk_engine.py        # weighted composite risk + attribution
│   │       └── heat_intelligence.py  # (Day 2) ranking + historical comparison
│   ├── scripts/
│   │   ├── fetch_boundaries.py       # OSM Overpass boundary fetcher
│   │   ├── refresh_weather.py        # Open-Meteo current+forecast -> SQLite
│   │   ├── refresh_historical.py     # (Day 2) 10-yr archive -> SQLite
│   │   ├── update_population.py       # verify/update town populations safely
│   │   ├── seed_mock_weather.py      # offline mock weather
│   │   └── seed_mock_historical.py   # (Day 2) offline mock baselines
│   └── tests/
│       ├── test_risk_engine.py
│       └── test_heat_intelligence.py # (Day 2)
├── data/
│   ├── geojson/
│   │   ├── lahore_towns.geojson          # active boundaries (fallback by default)
│   │   └── lahore_towns_fallback.geojson # approximate polygons
│   └── metadata/
│       └── town_metadata.json            # population, density, veg deficit, etc.
├── frontend/
│   ├── package.json
│   ├── next.config.js / tailwind.config.js / postcss.config.js
│   └── src/
│       ├── pages/ (index.js, _app.js)
│       ├── components/ (RiskMap, TownPanel, AlertsPanel, RankingPanel)
│       ├── lib/api.js
│       └── styles/globals.css
└── docs/
    ├── BUILD_PLAN.md            # the full 6-day plan
    ├── METHODOLOGY.md           # how the risk score works
    ├── DATA_SOURCES.md          # provenance + limitations
    └── ARCHITECTURE.md          # system design
```

---

## How the risk score works (short version)

Each town gets a **0–100 heat-risk score** = a weighted blend of four factors:

| Factor | Weight |
|---|---|
| Feels-like temperature (heat index) | 40% |
| Air temperature | 25% |
| Population density | 20% |
| Low vegetation / built-up density | 15% |

The model is **interpretable, not a black box** — every score decomposes into
the exact contribution of each factor, so a health officer can see *why* a town
is flagged. Full details in `docs/METHODOLOGY.md`.

---

## Data & honesty note

Population, area, and density are **official 2023 census figures** for Lahore's 5
tehsils (`verified: true` in `data/metadata/town_metadata.json`), and are
internally consistent (density = population / area). The only estimated field is
`vegetation_deficit` (a land-cover proxy, clearly labelled as such). Mock weather
and mock baselines are always clearly labelled — run `refresh_weather.py` /
`refresh_historical.py` for live data before the demo. See `docs/DATA_SOURCES.md`
and, if you ever change the figures, `docs/VERIFYING_POPULATION.md`.

This tool is a decision-support prototype, **not an official government
advisory**.

---

## Team

- **Member 1 — Data & Geospatial:** boundaries, Open-Meteo, SQLite, data pipeline
- **Member 2 — Risk Engine & AI:** heat index, scoring, attribution, alerts
- **Member 3 — Full Stack & UI:** FastAPI, Next.js, Leaflet, deployment

## License

Prepared for the Smart City Hackathon 2026.
