-- BMS LeadFlow — Week 7: Add contact/owner fields to companies table
-- Run this in Supabase SQL Editor

ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS contact_first_name   TEXT,
  ADD COLUMN IF NOT EXISTS contact_last_name    TEXT,
  ADD COLUMN IF NOT EXISTS contact_full_name    TEXT,
  ADD COLUMN IF NOT EXISTS contact_role         TEXT,
  ADD COLUMN IF NOT EXISTS contact_email        TEXT,
  ADD COLUMN IF NOT EXISTS email_confidence     INT,
  ADD COLUMN IF NOT EXISTS email_verified       BOOLEAN DEFAULT FALSE;

-- Index for email lookups
CREATE INDEX IF NOT EXISTS idx_companies_contact_email
  ON companies (contact_email)
  WHERE contact_email IS NOT NULL;
