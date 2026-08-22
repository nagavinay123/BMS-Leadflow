-- BMS LeadFlow — Week 8: Outreach Queue + Email Drafts
-- Run in Supabase SQL Editor

-- ── Outreach status on companies ──────────────────────────
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS outreach_status TEXT DEFAULT 'none',
  -- values: none | queued | emailed | replied | won | lost | suppressed
  ADD COLUMN IF NOT EXISTS outreach_queued_at  TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS outreach_emailed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS outreach_notes      TEXT;

-- ── Email drafts ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_drafts (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    UUID REFERENCES companies(id) ON DELETE CASCADE,
  subject       TEXT NOT NULL,
  body          TEXT NOT NULL,
  generated_at  TIMESTAMPTZ DEFAULT NOW(),
  edited        BOOLEAN DEFAULT FALSE,
  sent          BOOLEAN DEFAULT FALSE,
  sent_at       TIMESTAMPTZ,
  template_used TEXT
);

CREATE INDEX IF NOT EXISTS idx_email_drafts_company
  ON email_drafts(company_id);

-- RLS
ALTER TABLE email_drafts ENABLE ROW LEVEL SECURITY;

-- ── ICP Profiles (already created in Week 4 schema) ────────
-- Add sector and sic_code columns if missing
ALTER TABLE icp_profiles
  ADD COLUMN IF NOT EXISTS sic_codes   TEXT[],
  ADD COLUMN IF NOT EXISTS min_reviews INT  DEFAULT 0,
  ADD COLUMN IF NOT EXISTS min_rating  NUMERIC(2,1) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS active      BOOLEAN DEFAULT TRUE;
