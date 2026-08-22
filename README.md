# BMS LeadFlow
**BeMySocial Lead Generation Platform — Week 10 Build**

A full-stack, PECR-compliant cold-outreach pipeline that discovers UK businesses, matches them to Companies House, scores them, verifies contacts, and sends personalised email sequences — with a built-in approval gate and full dry-run safety mode.

> **Safety first:** `DRY_RUN=true` is the default. No real emails are sent until you explicitly set `DRY_RUN=false` and connect a warmed-up sending domain.

---

## Architecture overview

```
leadflow/
├── backend/
│   ├── main.py                  ← FastAPI server — all API endpoints
│   ├── pipeline.py              ← Discovery orchestrator (Maps → CH → score → verify)
│   ├── google_maps.py           ← Google Maps Places API
│   ├── companies_house.py       ← CH matching + director lookup
│   ├── website_checker.py       ← SSL, PageSpeed API, mobile score
│   ├── scoring.py               ← 40/30/30 ICP-fit / reachability / opportunity
│   ├── database.py              ← Supabase read/write layer
│   ├── email_verify.py          ← MillionVerifier integration + should_send() gate
│   ├── email_provider.py        ← Abstract provider + DryRunProvider factory
│   ├── smartlead_provider.py    ← Smartlead email platform adapter
│   ├── compliance.py            ← PECR gates, UK sending hours, footer builder
│   ├── campaign_engine.py       ← Send, follow-up scheduling, webhook processor
│   ├── email_templates.py       ← Initial + 2 follow-up templates
│   ├── claude_personalise.py    ← Claude Haiku opening-line generator (with safety check)
│   ├── .env.example             ← All required environment variables
│   ├── requirements.txt
│   └── tests/
│       ├── conftest.py          ← Safe test defaults (DRY_RUN=true, empty API keys)
│       ├── test_scoring.py
│       ├── test_email_verify.py
│       ├── test_suppression.py
│       ├── test_compliance.py
│       ├── test_deduplication.py
│       ├── test_webhooks.py
│       ├── test_scheduling.py
│       ├── test_ch_matching.py
│       └── test_ai_personalisation.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx                      ← Auth gate + tab router
│   │   ├── index.css
│   │   └── components/
│   │       ├── SearchForm.jsx           ← Discovery search
│   │       ├── CompanyTable.jsx         ← Sortable results
│   │       ├── StatsBar.jsx             ← Pipeline stats
│   │       ├── RunsHistory.jsx          ← Past runs
│   │       ├── CampaignMonitor.jsx      ← Campaign dashboard + budget
│   │       ├── ApprovalQueue.jsx        ← AI opening-line review
│   │       ├── CompliancePage.jsx       ← PECR gates + suppression list
│   │       └── LoginPage.jsx            ← Supabase Auth login
│   ├── .env.example
│   └── package.json
├── supabase/
│   ├── schema.sql               ← Original schema (Weeks 1–4)
│   └── migrations_week10.sql    ← Week 10 additions (run after schema.sql)
├── .gitignore
└── README.md
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | Backend runtime |
| Node.js 18+ | Frontend runtime |
| Supabase project | Free tier at supabase.com |
| Google Maps API key | Enable Places API (Legacy) in Cloud Console |
| Companies House API key | Free at developer.company-information.service.gov.uk |
| MillionVerifier API key | Email verification — app.millionverifier.com |
| Anthropic API key | Claude Haiku for personalisation — console.anthropic.com |
| Google PageSpeed key | Optional — console.cloud.google.com (enable PageSpeed Insights API) |
| Smartlead API key | Only needed when DRY_RUN=false and ready for live sending |

---

## One-time setup

### Step 1 — Clone and configure

```bash
git clone <your-repo-url>
cd leadflow

# Backend
cp backend/.env.example backend/.env

# Frontend
cp frontend/.env.example frontend/.env
```

Fill in `backend/.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...  # SERVICE ROLE key — NOT the anon key
GOOGLE_MAPS_API_KEY=AIza...
COMPANIES_HOUSE_API_KEY=...
MILLION_VERIFIER_API_KEY=...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_PAGESPEED_KEY=AIza...  # Optional — omit to use response-time fallback
SMARTLEAD_API_KEY=...         # Only needed when DRY_RUN=false

BMS_COMPANY_NUMBER=12345678
BMS_REGISTERED_ADDRESS=1 Example Street, London, EC1A 1BB
BMS_UNSUBSCRIBE_BASE_URL=https://your-app.com/unsubscribe

DRY_RUN=true   # KEEP THIS TRUE during development and testing
```

Fill in `frontend/.env`:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...   # ANON key only — never the service role key
VITE_API_BASE_URL=http://localhost:8000
```

> **NEVER commit `.env` to Git. NEVER paste secret values into Lovable prompts.**

### Step 2 — Set up the Supabase database

1. Open your Supabase project → SQL Editor
2. Run `supabase/schema.sql` (base tables)
3. Run `supabase/migrations_week10.sql` (contacts, campaigns, events, follow_ups, budget_log)

Enable Row-Level Security (RLS) on all tables — the migrations file includes the policies.

### Step 3 — Install dependencies

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

---

## Running the project

Open two terminal windows.

### Terminal 1 — Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Verify: `GET http://localhost:8000/health` → `{"status":"ok","version":"1.0.0"}`

Interactive API docs: `http://localhost:8000/docs`

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`

If `VITE_SUPABASE_URL` is set, you will see a login screen (Supabase Auth). Without it, the login screen is skipped (dev mode).

---

## Running the test suite

```bash
cd backend
python -m pytest tests/ -v
```

90 tests, all passing. Tests use mocked APIs — no real HTTP calls, no real database writes, no real emails.

---

## How the pipeline works

```
Google Maps → Companies House match → Website check (SSL + PageSpeed)
    → 40/30/30 Scoring → MillionVerifier email verification
    → Contacts table → Campaign membership → Compliance gates
    → DRY_RUN send (or real send) → Follow-up scheduling → Webhook events
```

### Scoring (40/30/30)

| Component | Max pts | Key signals |
|---|---|---|
| ICP Fit | 40 | CH matched, active status, ICP profile match, company age |
| Reachability | 30 | Email verified, named contact, email quality |
| Opportunity | 30 | Website issues found (no SSL, slow, no mobile, missing meta) |

**Threshold:** ≥ 60 required to enter a campaign.

### Email verification (MillionVerifier)

| MV result | Internal status | Can send? |
|---|---|---|
| ok | good | ✅ Yes |
| catch_all | catch_all | ✅ Yes |
| unknown | unverified | ❌ No |
| invalid / disposable / spamtrap | bad | ❌ No |
| role / mailbox_full | risky | ❌ No |

### PECR compliance gates (checked at send time)

1. Company is `ch_matched` and `company_status = active`
2. Contact email exists
3. Email status is `good` or `catch_all`
4. Email not in suppression list (checked at send time, not just discovery)
5. Campaign is `active`
6. Daily send limit not exceeded
7. Within UK sending hours: Mon–Fri 09:00–17:00 (skipped in dry-run)
8. Score ≥ 60

### Email sequence

| Step | When |
|---|---|
| Initial | On campaign send |
| Follow-up 1 | +4 business days (skips weekends) |
| Follow-up 2 | +11 business days (skips weekends) |

Auto-suppression: bounce or unsubscribe → added to suppression list + follow-ups cancelled.

### AI personalisation (Claude Haiku)

Generates a single opening line using only verified audit facts. Safety check: any output containing invented percentages (`\d{2,3}%`) is rejected and replaced with a rule-based fallback. All AI-generated opening lines go through the human approval queue before sending.

### Dry-run mode

When `DRY_RUN=true` (the default):
- All sends are logged to the console, not transmitted
- The sending-hours gate is skipped
- The `campaigns.dry_run` column defaults to `TRUE`
- No Smartlead API calls are made

When `DRY_RUN=false`:
- All 8 compliance gates are enforced
- Real emails are sent via Smartlead
- Requires a warmed-up inbox and a verified sending domain

---

## API reference

Full interactive docs at `http://localhost:8000/docs`. Key endpoints:

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/search` | Run discovery pipeline |
| POST | `/api/bulk-search` | Run multiple searches in sequence |
| GET | `/api/companies` | List companies (filter by run_id, status, score) |
| POST | `/api/verify-email` | Verify a single email with MillionVerifier |
| GET/POST | `/api/campaigns` | List / create campaigns |
| POST | `/api/campaigns/{id}/populate` | Add qualified companies as members |
| POST | `/api/send/{member_id}` | Send/dry-run email to one member |
| POST | `/api/process-follow-ups` | Batch-process due follow-ups |
| POST | `/api/webhook/email` | Receive events from Smartlead |
| GET | `/api/approval-queue` | List pending AI opening lines |
| POST | `/api/approval-queue/{id}` | Approve / reject / edit an opening line |
| POST | `/api/personalise/{company_id}` | Generate Claude opening line |
| GET | `/api/compliance/checklist` | System + manual compliance gate status |
| GET/POST | `/api/suppression` | View / add suppression entries |
| GET | `/api/budget` | Monthly budget summary |

---

## Dashboard tabs (frontend)

| Tab | Purpose |
|---|---|
| 🔍 Search | Run discovery searches |
| 📊 Results | View and sort scored companies |
| 📣 Campaigns | Monitor send stats, budget, events |
| ✅ Approval | Review and approve AI-generated opening lines |
| ⚖️ Compliance | System gate status + suppression list management |
| 📁 Runs | History of past discovery runs |

---

## Scheduled automation

Follow-up processing and campaign population can be automated via pg_cron (requires enabling pg_cron in Supabase dashboard). SQL stubs are included in `migrations_week10.sql` (commented out — uncomment once pg_cron is enabled).

Manual trigger via cron or n8n: `POST /api/process-follow-ups`

---

## Security checklist

- [x] `.env` in `.gitignore` — secrets never committed
- [x] `SUPABASE_SERVICE_KEY` never exposed to frontend
- [x] Frontend uses `VITE_SUPABASE_ANON_KEY` (anon key only)
- [x] RLS enabled on all Supabase tables
- [x] `DRY_RUN=true` default — no accidental live sends
- [x] `campaigns.dry_run` defaults to `TRUE` at DB level
- [x] Suppression checked at send time (not just at discovery)
- [x] AI outputs safety-checked — invented percentages trigger fallback
- [x] Webhook event deduplication via `provider_event_id` unique index
- [x] PECR footer mandatory on all outbound emails
- [x] UK business hours gate enforced in live mode

---

## Troubleshooting

**"Cannot reach the backend API"** — Start `uvicorn main:app --reload --port 8000`

**"SUPABASE_SERVICE_KEY must be set"** — Check `backend/.env`. Use the service role key, not the anon key.

**MV verification returns `unverified` for everything** — `MILLION_VERIFIER_API_KEY` is empty. Check `.env`.

**AI opening lines not generating** — `ANTHROPIC_API_KEY` is empty. Rule-based fallback is used automatically.

**PageSpeed scores missing** — `GOOGLE_PAGESPEED_KEY` not set. Response-time proxy is used; `mobile_score` will be `null`.

**Campaign stuck in `draft`** — Run `POST /api/campaigns/{id}/populate` to add members, then set status to `active`.

**Follow-ups not sending** — Check `POST /api/process-follow-ups` is being called on schedule.

---

## Team

| Role | Owner | Workstream |
|---|---|---|
| Data lead | Vinay | Google Maps API, scoring, repo |
| Pipeline lead | Arkana | Companies House, pipeline orchestration |
| Platform lead | Prashanth | Supabase, campaign engine, webhooks |
| Outreach lead | Prince | Frontend, email templates, AI personalisation |
| Compliance lead | Harika | PECR gates, suppression, compliance dashboard |

---

*BMS LeadFlow v1.0.0 — Week 10 | BeMySocial UEL placement team*
