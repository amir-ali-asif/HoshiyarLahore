# HoshiyarLahore
 
### Heatwave Early Warning for Health Authorities
 
**Smart City Hackathon 2026 · Theme: City Intelligence**
 
**Live demo:** _add your deployed Vercel URL here once live_
 
> *Hoshiyar* (ہوشیار) — Urdu for "alert, watchful, prepared."
 
HoshiyarLahore is a heatwave early-warning dashboard for public-health
authorities. It fuses live weather, official population data, and land-cover
data into an explainable, 0–100 heat-risk score for each of Lahore's five
administrative tehsils, forecasts that risk 72 hours ahead, and turns it into
concrete operational output — priority rankings, predictive alerts, and
copy-paste situation reports — so officials can pre-position cooling centres,
ORS supplies, and outreach teams **before** a heatwave hits, not after.
 
---
 
## Table of contents
 
- [What it does](#what-it-does)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Getting started](#getting-started)
  - [Option A — Instant preview, no setup](#option-a--instant-preview-no-setup)
  - [Option B — Run the full stack locally](#option-b--run-the-full-stack-locally)
- [Environment variables](#environment-variables)
- [API reference](#api-reference)
- [How the risk score works](#how-the-risk-score-works)
- [Data sources](#data-sources)
- [Running tests](#running-tests)
- [Deployment](#deployment)
- [Known limitations](#known-limitations)
- [Team](#team)
- [License](#license)
---
 
## What it does
 
- Scores **live heat risk (0–100)** for each of Lahore's five tehsils — Lahore
  City, Model Town, Shalimar, Lahore Cantonment, and Raiwind — using an
  interpretable weighted model, not a black box. Every score decomposes into
  the exact percentage each factor contributed.
- Forecasts that same risk score **72 hours ahead, hour by hour**, and surfaces
  **predictive lead-time alerts** ("Lahore City expected to reach Critical
  heat risk in ~13 hours").
- Compares today's forecast high against each tehsil's **10-year historical
  average** for that calendar date.
- Produces an ordered **priority-deployment ranking** across all five tehsils.
- Generates a **copy-paste situation report and a ≤160-character SMS brief**
  per tehsil, ready to forward to a field team.
- Shows a toggleable map layer of **candidate cooling-centre locations**
  (hospitals, parks, large venues).
- Includes a client-side **what-if simulator** — drag temperature/humidity
  sliders and watch the score, gauge, and attribution update live.
- **Auto-refreshes itself**: a background scheduler keeps live weather
  (hourly) and historical baselines (daily) current with no manual
  script-running, and reports its own data freshness honestly via an API
  endpoint.
- Ships with a **zero-setup static preview** (`preview.html`) so the full
  dashboard can be viewed with no backend running at all.
---
 
## Tech stack
 
| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (Pages Router), React, Tailwind CSS, Leaflet |
| Backend | FastAPI (Python 3), Uvicorn |
| Database | SQLite |
| Scheduling | APScheduler (in-process background jobs) |
| Geometry handling | Shapely |
| Weather data | Open-Meteo (current, forecast, historical archive) |
| Population/census data | Pakistan Bureau of Statistics, 2023 Census |
| Boundary/POI data | OpenStreetMap (via Overpass API) |
| Testing | pytest |
| Deployment | Render (backend), Vercel (frontend) |
 
---
 
## Project structure
 
```
hoshiyar-lahore/
├── README.md
├── preview.html                      # zero-setup static dashboard preview
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                   # FastAPI app + all API endpoints
│   │   ├── scheduler.py              # background auto-refresh scheduler
│   │   ├── db/
│   │   │   ├── schema.sql            # SQLite schema
│   │   │   └── database.py           # DB connection + town seeding
│   │   └── services/
│   │       ├── open_meteo.py         # Open-Meteo API client
│   │       ├── heat_index.py         # Rothfusz "feels-like" heat index
│   │       ├── risk_engine.py        # weighted risk score + attribution
│   │       ├── heat_intelligence.py  # ranking + historical comparison
│   │       ├── forecast.py           # 72h forecast risk + predictive alerts
│   │       └── situation_report.py   # SITREP / SMS brief generator
│   ├── scripts/
│   │   ├── fetch_boundaries.py       # fetch real tehsil boundaries from OSM
│   │   ├── fetch_cooling_centres.py  # fetch candidate cooling centres from OSM
│   │   ├── refresh_weather.py        # pull live weather into SQLite
│   │   ├── refresh_historical.py     # pull 10-year historical baselines
│   │   ├── seed_mock_weather.py      # offline mock weather (no internet needed)
│   │   ├── seed_mock_historical.py   # offline mock historical baselines
│   │   ├── update_population.py      # recompute/validate population figures
│   │   └── validate_data.py          # pre-demo data sanity check
│   └── tests/                        # pytest unit tests
├── data/
│   ├── geojson/
│   │   ├── lahore_towns.geojson          # active tehsil boundaries
│   │   ├── lahore_towns_fallback.geojson # approximate fallback polygons
│   │   ├── cooling_centres.geojson       # curated cooling-centre candidates
│   │   └── cooling_centres_fallback.geojson
│   └── metadata/
│       └── town_metadata.json        # population, area, density, veg deficit
└── frontend/
    ├── package.json
    ├── next.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── jsconfig.json
    └── src/
        ├── pages/
        │   ├── _app.js
        │   ├── _document.js
        │   └── index.js              # main dashboard page
        ├── components/
        │   ├── RiskMap.js
        │   ├── TownPanel.js
        │   ├── RiskGauge.js
        │   ├── AlertsPanel.js
        │   ├── PredictiveAlertsPanel.js
        │   ├── RankingPanel.js
        │   ├── ForecastTimeline.js
        │   ├── SituationReport.js
        │   └── WhatIfSlider.js
        ├── lib/
        │   ├── api.js                # backend API client
        │   └── riskEngine.js         # client-side port of the risk engine
        └── styles/
            └── globals.css
```
 
---
 
## Prerequisites
 
- **Python 3.11 or 3.12** (recommended — see note below)
- **Node.js 18+** and npm
- Internet access, if you want live weather data (optional — offline mock
  data is provided for everything)
> **Python version note:** `shapely==2.0.4` (pinned in `requirements.txt`)
> ships prebuilt wheels for Python 3.11 and 3.12. Very new Python versions
> (e.g. 3.13+) may not have a prebuilt wheel yet, forcing a slow/likely-failing
> source build. Use Python 3.11 or 3.12 locally, and pin the same version on
> whatever platform you deploy to.
 
---
 
## Getting started
 
### Option A — Instant preview, no setup
 
Open **`preview.html`** directly in any modern browser. It renders the full
dashboard UI against a bundled snapshot of mock data — no backend, no
`npm install`, nothing to run. (The interactive map tiles need internet to
load; the risk data, alerts, and detail panel all work fully offline.)
 
### Option B — Run the full stack locally
 
#### 1. Clone the repository
 
```bash
git clone https://github.com/amir-ali-asif/HoshiyarLahore.git
cd HoshiyarLahore
```
 
#### 2. Set up the backend
 
```bash
# From the repository root
python -m pip install -r backend/requirements.txt
```
 
**Initialise the database and load the five tehsils:**
 
```bash
python -m backend.app.db.database
```
 
**Load weather data** — pick one:
 
```bash
# Real live weather (needs internet, no API key required)
python backend/scripts/refresh_weather.py
 
# OR offline mock weather (works with no internet, clearly flagged as mock)
python backend/scripts/seed_mock_weather.py
```
 
**Load historical baselines** — pick one:
 
```bash
# Real 10-year Open-Meteo archive (needs internet, can take a few minutes)
python backend/scripts/refresh_historical.py
 
# OR offline mock baselines (instant, flagged with years_used = 0)
python backend/scripts/seed_mock_historical.py
```
 
**Start the backend API:**
 
```bash
uvicorn backend.app.main:app --reload --port 8000
```
 
This also starts the background auto-refresh scheduler, which keeps weather
(hourly) and historical baselines (daily) current automatically from this
point on — you do not need to re-run the scripts above manually while the
server is running.
 
Once running:
- API base: `http://localhost:8000`
- Interactive API docs (Swagger UI): `http://localhost:8000/docs`
#### 3. Set up the frontend
 
Open a **second terminal**:
 
```bash
cd frontend
npm install
```
 
Create a local environment file pointing at your backend:
 
```bash
echo "NEXT_PUBLIC_API_BASE=http://localhost:8000" > .env.local
```
 
Start the frontend dev server:
 
```bash
npm run dev
```
 
Visit **`http://localhost:3000`** in your browser.
 
#### 4. (Optional) Fetch real tehsil boundaries from OpenStreetMap
 
By default the app ships with approximate fallback tehsil boundaries. To try
pulling real administrative boundaries from OpenStreetMap:
 
```bash
python backend/scripts/fetch_boundaries.py
```
 
This overwrites `data/geojson/lahore_towns.geojson`. **Verify the result on
[geojson.io](https://geojson.io) before relying on it** — OSM's naming for
Lahore's tehsils is inconsistent and the fetch may fall back to the committed
approximate polygons.
 
#### 5. (Optional) Fetch cooling-centre candidates from OpenStreetMap
 
```bash
python backend/scripts/fetch_cooling_centres.py
```
 
This overwrites `data/geojson/cooling_centres.geojson` with hospitals, parks,
and large venues near each tehsil. A curated fallback set ships with the repo
so this layer works out of the box even without running the script.
 
---
 
## Environment variables
 
### Frontend (`frontend/.env.local`)
 
| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | Base URL of the backend API |
 
### Backend (optional, set before starting `uvicorn`)
 
| Variable | Default | Description |
|---|---|---|
| `HOSHIYAR_AUTO_REFRESH` | `1` | Set to `0` to disable the background auto-refresh scheduler entirely |
| `HOSHIYAR_REFRESH_MINUTES` | `60` | How often live weather refreshes, in minutes |
| `HOSHIYAR_HISTORICAL_HOURS` | `24` | How often the historical baseline refreshes, in hours |
 
Example:
 
```bash
HOSHIYAR_REFRESH_MINUTES=30 uvicorn backend.app.main:app --port 8000
```
 
---
 
## API reference
 
Full interactive documentation is auto-generated by FastAPI at
`http://localhost:8000/docs` once the backend is running. Summary:
 
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check + endpoint index |
| `GET` | `/api/towns` | All five tehsils with current risk + geometry (GeoJSON) |
| `GET` | `/api/towns/{town_id}` | Full detail for one tehsil: risk, weather, attribution, historical comparison |
| `GET` | `/api/towns/{town_id}/forecast` | 72-hour hourly risk forecast + daily peaks |
| `GET` | `/api/towns/{town_id}/sitrep` | Copy-paste situation report + SMS brief |
| `GET` | `/api/alerts` | Active alerts derived from current risk scores |
| `GET` | `/api/predictive-alerts` | Lead-time warnings from the 72h forecast |
| `GET` | `/api/ranking` | All tehsils ordered by priority for resource deployment |
| `GET` | `/api/cooling-centres` | Candidate cooling-centre locations (GeoJSON) |
| `GET` | `/api/overview` | Lahore-wide summary (average risk, exposed population, alert counts) |
| `GET` | `/api/status` | Data freshness + auto-refresh scheduler status |
| `POST` | `/api/refresh` | Force an immediate weather refresh |
 
---
 
## How the risk score works
 
Each tehsil gets a **0–100 heat-risk score**, computed as an interpretable
weighted composite:
 
$$
\text{score} = 0.40 \cdot n(\text{heat\_index}) + 0.25 \cdot n(\text{temperature}) + 0.20 \cdot n(\text{population\_density}) + 0.15 \cdot n(\text{vegetation\_deficit})
$$
 
where each \\( n(\cdot) \\) normalises a raw input to a 0–100 sub-score
against documented anchor points:
 
| Factor | Weight | 0 maps to | 100 maps to | Rationale |
|---|---|---|---|---|
| Feels-like temperature (heat index) | 40% | 27°C | 54°C | Most direct measure of danger to the human body |
| Air temperature | 25% | 30°C | 50°C | Absolute thermal stress, independent of humidity |
| Population density | 20% | 2,000/km² | 40,000/km² | More people exposed = higher public-health impact |
| Vegetation deficit (proxy) | 15% | 0.0 | 1.0 | Built-up, low-green areas trap heat (urban heat island) |
 
The heat index itself uses the **Rothfusz regression equation** — the same
formula used by the US National Weather Service — to convert air temperature
and humidity into a "feels-like" temperature.
 
**Severity bands:** 0–25 Low · 26–50 Moderate · 51–75 High · 76–100 Critical
 
**Alert thresholds:** Advisory `score > 45` · Warning `score > 60` · Critical `score > 75`
 
**Attribution:** because the score is a sum of weighted contributions, every
result reports exactly how many points — and what percentage — came from each
factor, e.g. *"Score: 84/100 (Critical) — Feels-like temperature 47%, Air
temperature 23%, Population density 16%, Low vegetation 14%."*
 
**Estimated exposed population** is a simple, transparent exposure proxy:
`exposure_factor = clamp((score - 25) / 75, 0, 1)`,
`estimated_exposed = tehsil_population × exposure_factor` — clearly labelled
as an estimate, not a claim about specific individuals.
 
The 40/25/20/15 weighting was validated two ways: across the five tehsils
under current live weather, scores spread by roughly **30 points**; and in a
controlled test holding weather **identical** across all tehsils (44°C, 30%
RH), scores still spread by roughly **17 points**, driven entirely by
population density and vegetation deficit — confirming the model captures
real neighbourhood vulnerability, not just a thermometer reading.
 
---
 
## Data sources
 
| Source | Used for | Access |
|---|---|---|
| [Open-Meteo](https://open-meteo.com/) | Live weather, 72-hour forecast, 10-year historical archive | Free REST API, no key required |
| Pakistan Bureau of Statistics — 2023 Census, Table 1 | Population, area, and density for all five tehsils | Official published census table |
| [OpenStreetMap](https://www.openstreetmap.org/) (via Overpass API) | Administrative boundaries, cooling-centre candidates | Free, ODbL-licensed |
| NWS Rothfusz regression | "Feels-like" heat index formula | Published, non-proprietary meteorological formula |
 
Population, area, and density figures are official 2023 census figures for
Lahore's five tehsils, internally consistent (density = population ÷ area,
exactly) and sum to Lahore District's official 2023 total of **13,004,135**:
 
| Tehsil | Area (km²) | Population (2023) | Density (/km²) |
|---|---|---|---|
| Lahore City | 214 | 4,123,354 | 19,268 |
| Model Town | 353 | 3,244,906 | 9,192 |
| Shalimar | 272 | 2,670,140 | 9,817 |
| Lahore Cantonment | 466 | 1,885,098 | 4,045 |
| Raiwind | 467 | 1,080,637 | 2,314 |
 
The only estimated field is `vegetation_deficit` — a land-cover proxy, clearly
labelled as an estimate throughout the API and UI. Mock/seed weather and
historical data are always clearly flagged as such (never presented as live
data). Cooling centres are shown as **candidates for placement**, not
officially designated centres.
 
To re-verify or update population figures, edit
`data/metadata/town_metadata.json` and run:
 
```bash
python backend/scripts/update_population.py
```
 
This recomputes `population_density = population / area_km2` for every
tehsil and flags anything inconsistent. Then reload the database:
 
```bash
python -m backend.app.db.database
```
 
---
 
## Running tests
 
```bash
cd HoshiyarLahore
python -m pytest backend/tests/ -v
```
 
The test suite covers the risk engine, 72-hour forecast logic, historical
comparison/ranking, and situation-report generation.
 
Before a live demo, it's also worth running the data validation script, which
checks metadata completeness, density consistency, geometry coverage, and
database freshness in one pass:
 
```bash
python backend/scripts/validate_data.py
```
 
---
 
## Deployment
 
- **Backend → Render** (or any host that runs a persistent process, e.g.
  Railway). The backend's background auto-refresh scheduler requires the
  process to stay alive continuously — it will **not** work on serverless
  hosting (e.g. Vercel serverless functions, AWS Lambda), since those spin up
  a fresh instance per request and don't keep a background thread running
  between requests.
  - Build command: `pip install -r backend/requirements.txt`
  - Start command: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
  - Pin the Python version to **3.11 or 3.12** (e.g. via a `runtime.txt` file
    at the repo root, or the platform's Python-version environment variable)
    to ensure `shapely` installs from a prebuilt wheel.
- **Frontend → Vercel.**
  - Since the Next.js app lives inside the `frontend/` subfolder rather than
    the repository root, set the project's **Root Directory** to `frontend`
    in the Vercel dashboard (Settings → General).
  - Set the `NEXT_PUBLIC_API_BASE` environment variable to your deployed
    backend URL.
---
 
## Known limitations
 
- **Vegetation deficit** is currently a reasoned per-tehsil proxy estimate
  (old dense city ≈ 0.88, greener planned areas ≈ 0.55, peri-urban ≈ 0.45),
  not yet derived from satellite NDVI.
- **Weather is fetched at each tehsil's centroid** and applied tehsil-wide —
  a reasonable simplification for five large administrative units, not a
  fine-grained grid.
- **The 40/25/20/15 weighting is a reasoned, documented starting point**, not
  empirically fitted to Lahore heat-outcome data, which isn't openly
  available at tehsil level.
- **Tehsil boundaries** are approximate fallback polygons unless
  `fetch_boundaries.py` has been run and its output verified.
- On free-tier hosting (e.g. Render's free plan), the backend process can
  spin down after periods of inactivity; the auto-refresh scheduler only
  runs while the process is awake, though it re-fetches current data
  immediately on every cold start.
This tool is a decision-support prototype, **not an official government
advisory**.
 
---
 
## Team
 
- **Member 1 — Data & Geospatial:** boundaries, Open-Meteo integration, SQLite, data pipeline
- **Member 2 — Risk Engine & AI:** heat index, scoring model, attribution, alerts
- **Member 3 — Full Stack & UI:** FastAPI backend, Next.js frontend, Leaflet map, deployment
## License
 
Prepared for the Smart City Hackathon 2026.