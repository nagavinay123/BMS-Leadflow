# BMS LeadFlow
**BeMySocial Lead Generation Platform — Week 4 Build**

A full-stack pipeline that finds UK businesses by type and town, matches them to Companies House, and displays a ranked results table.

---

## Project structure

```
leadflow/
├── backend/
│   ├── main.py              ← FastAPI server (start this first)
│   ├── pipeline.py          ← Discovery pipeline orchestrator
│   ├── google_maps.py       ← Google Maps Places API (Vinay)
│   ├── companies_house.py   ← Companies House matching (Arkana)
│   ├── database.py          ← Supabase read/write layer (Prashanth)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                        ← Main app + state
│   │   ├── index.css                      ← All styles
│   │   └── components/
│   │       ├── SearchForm.jsx             ← Search inputs
│   │       ├── StatsBar.jsx               ← Pipeline stats
│   │       ├── CompanyTable.jsx           ← Sortable results table
│   │       └── RunsHistory.jsx            ← Past runs view
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── supabase/
│   └── schema.sql           ← Run this in Supabase SQL Editor
├── .env.example             ← Copy to .env and fill in keys
├── .gitignore
└── README.md
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- A Supabase project (free tier at supabase.com)
- A Google Maps API key (free tier at console.cloud.google.com)
- A Companies House API key (free at developer.company-information.service.gov.uk)

---

## One-time setup (do this once)

### Step 1 — Clone and configure

```bash
git clone <your-repo-url>
cd leadflow

# Copy the env template
cp .env.example .env
```

Open `.env` and fill in:
- `SUPABASE_URL` — from Supabase dashboard → Project Settings → API
- `SUPABASE_SERVICE_KEY` — the **service role** key (not anon)
- `GOOGLE_MAPS_API_KEY` — from Google Cloud Console (enable Places API legacy)
- `COMPANIES_HOUSE_API_KEY` — from Companies House developer portal (free)

**Never commit `.env` to Git. Never paste keys into Lovable prompts.**

### Step 2 — Set up the Supabase database

1. Open your Supabase project at supabase.com
2. Go to SQL Editor
3. Open `supabase/schema.sql`
4. Paste the entire contents and click Run

This creates all the tables: `companies`, `discovery_runs`, `suppression_list`, `icp_profiles`, `decisions_log`.

### Step 3 — Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### Step 4 — Install frontend dependencies

```bash
cd frontend
npm install
```

---

## Running the project

You need two terminal windows — one for the backend, one for the frontend.

### Terminal 1 — Backend (FastAPI)

```bash
cd backend
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

Verify it works: open http://localhost:8000/health in your browser.
You should see: `{"status":"ok","version":"0.4.0"}`

### Terminal 2 — Frontend (React + Vite)

```bash
cd frontend
npm run dev
```

You should see:
```
  VITE v5.x.x  ready in xxx ms
  ➜  Local:   http://localhost:5173/
```

Open http://localhost:5173 in your browser.

---

## How to use it

1. **Open** http://localhost:5173
2. **Type a business type** — e.g. `plumber`, `accountant`, `estate agent`
3. **Type a UK town** — e.g. `Leeds`, `Manchester`, `Bristol`
4. **Set max results** (10–60; Google's hard cap is 60)
5. **Click "Find Leads"**

The pipeline runs:
- Searches Google Maps → up to 60 businesses
- Fetches full details for each (phone, website, rating)
- Matches each to Companies House (active, incorporated entities only)
- Stores everything in Supabase
- Returns results to the table

⏳ **This takes 1–3 minutes for 50 companies.** The loading screen tells you this. Don't refresh — wait for it.

### What the table shows

| Column | What it is |
|---|---|
| Business | Google Maps name. Clickable if they have a website. |
| Registered Name | Official name from Companies House |
| Company No. | Links directly to Companies House profile |
| Type | ltd, llp, plc etc. |
| Address | Registered address |
| Website | ✓ Yes / ✗ None |
| CH Match | Whether we matched to Companies House |
| Rating | Google star rating |
| Reviews | Number of Google reviews |
| Score | Pipeline score 0–100 (scoring engine week 5+) |

Click any column header to sort. Use the filter box to search by name, company number, or address.

---

## Running the pipeline from the command line (no frontend needed)

```bash
cd backend
python pipeline.py --type "plumber" --town "Leeds" --max 50
```

This runs the full pipeline and prints results to the terminal. Useful for testing without the UI.

---

## API endpoints

The FastAPI server exposes these endpoints. You can test them at http://localhost:8000/docs (auto-generated Swagger UI).

| Method | Endpoint | What it does |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/search` | Trigger discovery pipeline |
| GET | `/api/companies` | List companies (filter by run_id, status) |
| GET | `/api/runs` | List discovery runs |
| GET | `/api/stats` | Pipeline counts and percentages |
| GET | `/api/suppression` | View suppression list |
| POST | `/api/suppression` | Add to suppression list |

---

## Troubleshooting

**"Cannot reach the backend API"** — Start the FastAPI server (Terminal 1 above).

**"SUPABASE_URL and SUPABASE_SERVICE_KEY must be set"** — Check your `.env` file has the correct values with no extra spaces.

**"Google Maps API error: REQUEST_DENIED"** — Your API key is wrong, or the Places API is not enabled in Google Cloud Console.

**Pipeline returns 0 results** — Try a more common business type or a larger UK city.

**Companies House returns no matches** — This is normal. Many Google Maps listings are sole traders or have different registered names. The pipeline still stores them with `ch_matched = false`.

**Supabase insert error "unique constraint"** — The company is already in the database from a previous run. This is handled by upsert — it updates the existing record.

---

## Week-by-week build plan

| Week | What's added |
|---|---|
| 3 ✅ | Repo, Supabase schema, Lovable page, API keys |
| 4 ✅ | **This build** — company search, CH matching, results table |
| 5 | Website checker (SSL, PageSpeed, mobile) |
| 6 | **Demo 1** — scoring, ranked table, fully automated |
| 7 | Contact enrichment, named person, verified email |
| 8 | Dashboard v1 — stage counts, prospect table |
| 9 | Email drafts, approval flow, Smartlead/Instantly |
| 10 | End-to-end test at volume |
| 11 | Polish, docs, cost tracking |
| 12 | Final demo prep |
| 13 | Final demo and handover |

---

## Team

| Role | Owner | Workstream |
|---|---|---|
| Data lead | Vinay | Google Maps API, repo structure |
| Pipeline lead | Arkana | Companies House matching, company matching function |
| Platform lead | Prashanth | Supabase schema, n8n, database layer |
| Outreach lead | Prince | Lovable frontend, email verification |
| Compliance lead | Harika | n8n webhooks, API response quality |

---

*BMS LeadFlow v0.4.0 — Week 4 | Prepared for BeMySocial UEL placement team*
