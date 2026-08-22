-- BMS LeadFlow — add social media columns to companies
-- Run in Supabase SQL Editor

ALTER TABLE companies ADD COLUMN IF NOT EXISTS instagram_url text;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS facebook_url  text;
