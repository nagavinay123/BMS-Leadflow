-- ============================================================
-- BMS LeadFlow — Supabase Schema
-- Week 4 | Run this in Supabase SQL Editor
-- ============================================================

-- Enable UUID generation
create extension if not exists "pgcrypto";


-- ──────────────────────────────────────────────
-- ICP Profiles
-- ──────────────────────────────────────────────
create table if not exists icp_profiles (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  sic_codes     text[],
  regions       text[],
  size_band     text,
  signals       jsonb default '{}',
  exclusions    jsonb default '{}',
  created_at    timestamptz not null default now()
);


-- ──────────────────────────────────────────────
-- Discovery Runs
-- ──────────────────────────────────────────────
create table if not exists discovery_runs (
  id              uuid primary key default gen_random_uuid(),
  icp_id          uuid references icp_profiles(id) on delete set null,
  source          text not null,
  query           jsonb not null default '{}',
  results_count   integer not null default 0,
  est_cost_usd    numeric(8,4) not null default 0,
  status          text not null default 'running'
                  check (status in ('running','complete','failed')),
  error           text,
  ran_at          timestamptz not null default now()
);


-- ──────────────────────────────────────────────
-- Companies  (one row per business)
-- ──────────────────────────────────────────────
create table if not exists companies (
  id                  uuid primary key default gen_random_uuid(),

  -- Identity
  name                text not null,
  domain              text,
  company_number      text,                  -- from Companies House
  google_place_id     text unique,           -- dedup key for Google Maps

  -- Companies House data
  registered_name     text,
  registered_address  text,
  incorporation_date  date,
  company_status      text,                  -- active, dissolved …
  company_type        text,                  -- ltd, llp, plc …
  sic_codes           text[],
  ch_matched          boolean not null default false,

  -- Google Maps data
  phone               text,
  website             text,
  rating              numeric(3,1),
  review_count        integer,
  has_website         boolean not null default false,

  -- Pipeline
  source              text not null,         -- google_maps, companies_house
  source_url          text,
  discovery_run_id    uuid references discovery_runs(id) on delete set null,
  icp_id              uuid references icp_profiles(id) on delete set null,
  status              text not null default 'discovered'
                      check (status in (
                        'discovered','enriched','verified',
                        'queued','contacted',
                        'replied','bounced','unsubscribed'
                      )),
  score               integer not null default 0,

  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

-- Unique constraints (nullable columns need partial indexes)
create unique index if not exists companies_company_number_idx
  on companies (company_number)
  where company_number is not null;

create unique index if not exists companies_domain_idx
  on companies (domain)
  where domain is not null;

-- Auto-update updated_at
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists companies_updated_at on companies;
create trigger companies_updated_at
  before update on companies
  for each row execute function set_updated_at();


-- ──────────────────────────────────────────────
-- Suppression List  (never deleted from)
-- ──────────────────────────────────────────────
create table if not exists suppression_list (
  id              uuid primary key default gen_random_uuid(),
  email           text,
  domain          text,
  company_number  text,
  reason          text not null default 'manual',
  added_at        timestamptz not null default now()
);

create index if not exists suppression_domain_idx   on suppression_list (domain);
create index if not exists suppression_email_idx    on suppression_list (email);
create index if not exists suppression_number_idx   on suppression_list (company_number);


-- ──────────────────────────────────────────────
-- Decisions Log
-- ──────────────────────────────────────────────
create table if not exists decisions_log (
  id                  uuid primary key default gen_random_uuid(),
  decision_date       date not null default current_date,
  decision            text not null,
  options_considered  text,
  made_by             text,
  created_at          timestamptz not null default now()
);


-- ──────────────────────────────────────────────
-- Row Level Security (basic — team + service key only)
-- ──────────────────────────────────────────────
alter table icp_profiles     enable row level security;
alter table discovery_runs   enable row level security;
alter table companies        enable row level security;
alter table suppression_list enable row level security;
alter table decisions_log    enable row level security;

-- Service key bypasses RLS — used by the Python backend
-- Anon key has NO access (dashboard auth is handled separately)
-- For local dev, you can temporarily disable RLS:
-- alter table companies disable row level security;
