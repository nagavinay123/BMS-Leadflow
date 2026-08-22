-- ============================================================
-- BMS LeadFlow — Week 10 Complete Migration
-- Run this AFTER the existing schema.sql and all add_*.sql files
-- Safe to re-run: uses IF NOT EXISTS / CREATE OR REPLACE
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- 0. Extensions
-- ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_cron";   -- for scheduled jobs (enable in Supabase dashboard first)

-- ──────────────────────────────────────────────────────────────
-- 1. Patch existing companies columns (safe)
-- ──────────────────────────────────────────────────────────────
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS icp_match        TEXT,
  ADD COLUMN IF NOT EXISTS icp_score_bonus  INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS contact_first_name   TEXT,
  ADD COLUMN IF NOT EXISTS contact_last_name    TEXT,
  ADD COLUMN IF NOT EXISTS contact_full_name    TEXT,
  ADD COLUMN IF NOT EXISTS contact_role         TEXT,
  ADD COLUMN IF NOT EXISTS contact_email        TEXT,
  ADD COLUMN IF NOT EXISTS email_confidence     INTEGER,
  ADD COLUMN IF NOT EXISTS email_verified       BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS outreach_status      TEXT DEFAULT 'none',
  ADD COLUMN IF NOT EXISTS outreach_queued_at   TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS outreach_emailed_at  TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS outreach_notes       TEXT,
  ADD COLUMN IF NOT EXISTS instagram_url        TEXT,
  ADD COLUMN IF NOT EXISTS facebook_url         TEXT,
  ADD COLUMN IF NOT EXISTS twitter_url          TEXT,
  ADD COLUMN IF NOT EXISTS linkedin_url         TEXT;

-- Performance indexes on companies
CREATE INDEX IF NOT EXISTS idx_companies_score        ON companies (score DESC);
CREATE INDEX IF NOT EXISTS idx_companies_status       ON companies (status);
CREATE INDEX IF NOT EXISTS idx_companies_outreach     ON companies (outreach_status);
CREATE INDEX IF NOT EXISTS idx_companies_ch_matched   ON companies (ch_matched);
CREATE INDEX IF NOT EXISTS idx_companies_contact_email
  ON companies (contact_email) WHERE contact_email IS NOT NULL;

-- ──────────────────────────────────────────────────────────────
-- 2. Patch icp_profiles
-- ──────────────────────────────────────────────────────────────
ALTER TABLE icp_profiles
  ADD COLUMN IF NOT EXISTS description        TEXT,
  ADD COLUMN IF NOT EXISTS business_types     TEXT[],
  ADD COLUMN IF NOT EXISTS keywords           TEXT[],
  ADD COLUMN IF NOT EXISTS min_reviews        INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS min_rating         NUMERIC(2,1) DEFAULT 0,
  ADD COLUMN IF NOT EXISTS active             BOOLEAN DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS min_company_age_years INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS updated_at         TIMESTAMPTZ DEFAULT NOW();

-- ──────────────────────────────────────────────────────────────
-- 3. Website audits (ensure exists)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS website_audits (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id          UUID REFERENCES companies(id) ON DELETE CASCADE,
  resolves            BOOLEAN,
  https               BOOLEAN,
  has_viewport        BOOLEAN,
  has_title           BOOLEAN,
  has_meta_description BOOLEAN,
  performance_score   INTEGER,
  mobile_score        INTEGER,
  response_time_ms    INTEGER,
  page_title          TEXT,
  meta_description    TEXT,
  issues              JSONB DEFAULT '[]',
  emails_found        TEXT[],
  social_links        JSONB DEFAULT '{}',
  audit_source        TEXT DEFAULT 'response_time',  -- 'pagespeed' | 'response_time'
  error               TEXT,
  audited_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_website_audits_company ON website_audits (company_id);
ALTER TABLE website_audits ENABLE ROW LEVEL SECURITY;

-- ──────────────────────────────────────────────────────────────
-- 4. Email Drafts (ensure exists, add AI columns)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_drafts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      UUID REFERENCES companies(id) ON DELETE CASCADE,
  subject         TEXT NOT NULL,
  body            TEXT NOT NULL,
  generated_at    TIMESTAMPTZ DEFAULT NOW(),
  edited          BOOLEAN DEFAULT FALSE,
  sent            BOOLEAN DEFAULT FALSE,
  sent_at         TIMESTAMPTZ,
  template_used   TEXT
);
ALTER TABLE email_drafts
  ADD COLUMN IF NOT EXISTS ai_opening       TEXT,
  ADD COLUMN IF NOT EXISTS ai_model         TEXT,
  ADD COLUMN IF NOT EXISTS ai_generated_at  TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS approval_status  TEXT DEFAULT 'pending'
    CHECK (approval_status IN ('pending','approved','rejected','skipped')),
  ADD COLUMN IF NOT EXISTS approved_by      TEXT,
  ADD COLUMN IF NOT EXISTS approved_at      TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_email_drafts_company    ON email_drafts (company_id);
CREATE INDEX IF NOT EXISTS idx_email_drafts_approval   ON email_drafts (approval_status);
ALTER TABLE email_drafts ENABLE ROW LEVEL SECURITY;

-- ──────────────────────────────────────────────────────────────
-- 5. CONTACTS
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS contacts (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id        UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  first_name        TEXT,
  last_name         TEXT,
  full_name         TEXT,
  role              TEXT,
  email             TEXT,
  email_status      TEXT NOT NULL DEFAULT 'unverified'
    CHECK (email_status IN ('unverified','good','catch_all','bad','risky')),
  email_verified_at TIMESTAMPTZ,
  email_confidence  INTEGER,
  linkedin_url      TEXT,
  source            TEXT NOT NULL DEFAULT 'companies_house'
    CHECK (source IN ('companies_house','hunter','homepage','manual','linkedin')),
  is_primary        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contacts_company      ON contacts (company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_email        ON contacts (email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_email_status ON contacts (email_status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_company_email
  ON contacts (company_id, email) WHERE email IS NOT NULL;

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS contacts_updated_at ON contacts;
CREATE TRIGGER contacts_updated_at
  BEFORE UPDATE ON contacts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;

-- ──────────────────────────────────────────────────────────────
-- 6. CAMPAIGNS
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS campaigns (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name             TEXT NOT NULL,
  description      TEXT,
  status           TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','active','paused','completed','cancelled')),
  icp_id           UUID REFERENCES icp_profiles(id) ON DELETE SET NULL,
  sender_name      TEXT NOT NULL DEFAULT 'James',
  sender_email     TEXT,
  reply_to_email   TEXT,
  daily_limit      INTEGER NOT NULL DEFAULT 25,
  weekly_budget    NUMERIC(8,2) DEFAULT 0,
  dry_run          BOOLEAN NOT NULL DEFAULT TRUE,   -- SAFETY: TRUE by default
  -- running metrics (updated by webhook events)
  total_sent        INTEGER NOT NULL DEFAULT 0,
  total_opened      INTEGER NOT NULL DEFAULT 0,
  total_clicked     INTEGER NOT NULL DEFAULT 0,
  total_replied     INTEGER NOT NULL DEFAULT 0,
  total_bounced     INTEGER NOT NULL DEFAULT 0,
  total_unsubscribed INTEGER NOT NULL DEFAULT 0,
  -- timestamps
  started_at       TIMESTAMPTZ,
  completed_at     TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS campaigns_updated_at ON campaigns;
CREATE TRIGGER campaigns_updated_at
  BEFORE UPDATE ON campaigns
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns (status);
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;

-- ──────────────────────────────────────────────────────────────
-- 7. CAMPAIGN MEMBERS
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS campaign_members (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id         UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  contact_id          UUID REFERENCES contacts(id) ON DELETE SET NULL,
  email_draft_id      UUID REFERENCES email_drafts(id) ON DELETE SET NULL,
  status              TEXT NOT NULL DEFAULT 'queued'
    CHECK (status IN (
      'queued','approved','sending','sent',
      'replied','bounced','unsubscribed','completed','stopped','error'
    )),
  sequence_step       INTEGER NOT NULL DEFAULT 1,  -- 1=initial, 2=followup1, 3=followup2
  next_follow_up      TIMESTAMPTZ,
  stopped_reason      TEXT,
  provider_thread_id  TEXT,  -- Smartlead thread / campaign member ID
  -- timestamps
  queued_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sent_at             TIMESTAMPTZ,
  replied_at          TIMESTAMPTZ,
  bounced_at          TIMESTAMPTZ,
  unsubscribed_at     TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_campaign_members_unique
  ON campaign_members (campaign_id, company_id);
CREATE INDEX IF NOT EXISTS idx_campaign_members_campaign   ON campaign_members (campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_members_status     ON campaign_members (status);
CREATE INDEX IF NOT EXISTS idx_campaign_members_followup   ON campaign_members (next_follow_up)
  WHERE next_follow_up IS NOT NULL AND status NOT IN ('replied','bounced','unsubscribed','stopped');

DROP TRIGGER IF EXISTS campaign_members_updated_at ON campaign_members;
CREATE TRIGGER campaign_members_updated_at
  BEFORE UPDATE ON campaign_members
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE campaign_members ENABLE ROW LEVEL SECURITY;

-- ──────────────────────────────────────────────────────────────
-- 8. EVENTS
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id         UUID REFERENCES campaigns(id) ON DELETE SET NULL,
  campaign_member_id  UUID REFERENCES campaign_members(id) ON DELETE SET NULL,
  company_id          UUID REFERENCES companies(id) ON DELETE SET NULL,
  contact_id          UUID REFERENCES contacts(id) ON DELETE SET NULL,
  event_type          TEXT NOT NULL
    CHECK (event_type IN ('sent','open','click','reply','bounce','unsubscribe','error')),
  provider_event_id   TEXT,   -- dedup key from Smartlead/Instantly
  email               TEXT,
  subject             TEXT,
  metadata            JSONB DEFAULT '{}',
  occurred_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_events_provider_dedup
  ON events (provider_event_id) WHERE provider_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_campaign       ON events (campaign_id);
CREATE INDEX IF NOT EXISTS idx_events_member         ON events (campaign_member_id);
CREATE INDEX IF NOT EXISTS idx_events_type           ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_occurred       ON events (occurred_at DESC);

ALTER TABLE events ENABLE ROW LEVEL SECURITY;

-- ──────────────────────────────────────────────────────────────
-- 9. FOLLOW UPS
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS follow_ups (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_member_id  UUID NOT NULL REFERENCES campaign_members(id) ON DELETE CASCADE,
  campaign_id         UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  company_id          UUID REFERENCES companies(id) ON DELETE SET NULL,
  contact_id          UUID REFERENCES contacts(id) ON DELETE SET NULL,
  sequence_step       INTEGER NOT NULL,  -- 2 or 3
  scheduled_at        TIMESTAMPTZ NOT NULL,
  sent_at             TIMESTAMPTZ,
  cancelled_at        TIMESTAMPTZ,
  cancel_reason       TEXT,   -- 'reply' | 'bounce' | 'unsubscribe' | 'campaign_paused' | 'manual'
  status              TEXT NOT NULL DEFAULT 'scheduled'
    CHECK (status IN ('scheduled','sent','cancelled','error')),
  email_draft_id      UUID REFERENCES email_drafts(id) ON DELETE SET NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_follow_ups_member     ON follow_ups (campaign_member_id);
CREATE INDEX IF NOT EXISTS idx_follow_ups_scheduled  ON follow_ups (scheduled_at)
  WHERE status = 'scheduled';

ALTER TABLE follow_ups ENABLE ROW LEVEL SECURITY;

-- ──────────────────────────────────────────────────────────────
-- 10. BUDGET LOG
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS budget_log (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id  UUID REFERENCES campaigns(id) ON DELETE SET NULL,
  provider     TEXT NOT NULL,   -- 'smartlead' | 'instantly' | 'millionverifier' | 'apify' | 'hunter' | 'pagespeed' | 'anthropic'
  amount       NUMERIC(8,4) NOT NULL,
  currency     TEXT NOT NULL DEFAULT 'GBP',
  description  TEXT,
  occurred_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_budget_log_campaign    ON budget_log (campaign_id);
CREATE INDEX IF NOT EXISTS idx_budget_log_occurred    ON budget_log (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_budget_log_provider    ON budget_log (provider);

ALTER TABLE budget_log ENABLE ROW LEVEL SECURITY;

-- ──────────────────────────────────────────────────────────────
-- 11. RLS POLICIES — service key bypasses, anon blocked
-- ──────────────────────────────────────────────────────────────
-- Pattern: allow all for authenticated role (used by service key in backend)
-- The service key runs as 'service_role' which bypasses RLS automatically.
-- These policies protect against anon/public access via the anon key.

-- contacts
DROP POLICY IF EXISTS contacts_service_all ON contacts;
CREATE POLICY contacts_service_all ON contacts
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- campaigns
DROP POLICY IF EXISTS campaigns_service_all ON campaigns;
CREATE POLICY campaigns_service_all ON campaigns
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- campaign_members
DROP POLICY IF EXISTS campaign_members_service_all ON campaign_members;
CREATE POLICY campaign_members_service_all ON campaign_members
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- events
DROP POLICY IF EXISTS events_service_all ON events;
CREATE POLICY events_service_all ON events
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- follow_ups
DROP POLICY IF EXISTS follow_ups_service_all ON follow_ups;
CREATE POLICY follow_ups_service_all ON follow_ups
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- budget_log
DROP POLICY IF EXISTS budget_log_service_all ON budget_log;
CREATE POLICY budget_log_service_all ON budget_log
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- existing tables
DROP POLICY IF EXISTS companies_service_all ON companies;
CREATE POLICY companies_service_all ON companies
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS suppression_service_all ON suppression_list;
CREATE POLICY suppression_service_all ON suppression_list
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS icp_service_all ON icp_profiles;
CREATE POLICY icp_service_all ON icp_profiles
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS website_audits_service_all ON website_audits;
CREATE POLICY website_audits_service_all ON website_audits
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS email_drafts_service_all ON email_drafts;
CREATE POLICY email_drafts_service_all ON email_drafts
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS discovery_runs_service_all ON discovery_runs;
CREATE POLICY discovery_runs_service_all ON discovery_runs
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS decisions_log_service_all ON decisions_log;
CREATE POLICY decisions_log_service_all ON decisions_log
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- ──────────────────────────────────────────────────────────────
-- 12. HELPER VIEWS
-- ──────────────────────────────────────────────────────────────

-- Monthly budget summary
CREATE OR REPLACE VIEW v_monthly_budget AS
SELECT
  DATE_TRUNC('month', occurred_at) AS month,
  provider,
  SUM(amount) AS total_spent,
  currency
FROM budget_log
GROUP BY 1, 2, 4
ORDER BY 1 DESC, 3 DESC;

-- Campaign performance overview
CREATE OR REPLACE VIEW v_campaign_stats AS
SELECT
  c.id,
  c.name,
  c.status,
  c.dry_run,
  c.daily_limit,
  c.weekly_budget,
  COUNT(cm.id)                                      AS member_count,
  COUNT(cm.id) FILTER (WHERE cm.status = 'sent')   AS sent,
  COUNT(e.id)  FILTER (WHERE e.event_type = 'open') AS opens,
  COUNT(e.id)  FILTER (WHERE e.event_type = 'click') AS clicks,
  COUNT(e.id)  FILTER (WHERE e.event_type = 'reply') AS replies,
  COUNT(e.id)  FILTER (WHERE e.event_type = 'bounce') AS bounces,
  COUNT(e.id)  FILTER (WHERE e.event_type = 'unsubscribe') AS unsubscribes,
  COALESCE((SELECT SUM(amount) FROM budget_log bl WHERE bl.campaign_id = c.id), 0) AS total_cost_gbp
FROM campaigns c
LEFT JOIN campaign_members cm ON cm.campaign_id = c.id
LEFT JOIN events e ON e.campaign_id = c.id
GROUP BY c.id;

-- ──────────────────────────────────────────────────────────────
-- 13. pg_cron scheduled jobs (only if pg_cron extension is enabled)
-- ──────────────────────────────────────────────────────────────
-- Uncomment and run manually once pg_cron is enabled in Supabase dashboard
-- These call the Edge Functions defined in supabase/functions/

-- SELECT cron.schedule('follow-up-processor', '*/15 * * * *',
--   $$SELECT net.http_post(url:='https://YOUR_PROJECT.supabase.co/functions/v1/process-follow-ups',
--     headers:='{"Authorization": "Bearer YOUR_SERVICE_KEY"}'::jsonb, body:='{}'::jsonb)$$
-- );

-- SELECT cron.schedule('discovery-nightly', '0 2 * * 1-5',
--   $$SELECT net.http_post(url:='https://YOUR_PROJECT.supabase.co/functions/v1/run-discovery',
--     headers:='{"Authorization": "Bearer YOUR_SERVICE_KEY"}'::jsonb, body:='{}'::jsonb)$$
-- );
