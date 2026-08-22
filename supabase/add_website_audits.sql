-- ============================================================
-- BMS LeadFlow — Week 5 Migration
-- Adds: website_audits table
-- Run this in Supabase SQL Editor AFTER schema.sql
-- ============================================================

create table if not exists website_audits (
  id                   uuid primary key default gen_random_uuid(),
  company_id           uuid references companies(id) on delete cascade,

  -- Basic checks
  domain               text,
  resolves             boolean not null default false,   -- site is reachable
  https                boolean not null default false,   -- SSL present

  -- Google PageSpeed Insights scores (0–100)
  performance_score    integer,   -- desktop performance
  mobile_score         integer,   -- mobile performance

  -- Page quality signals
  has_viewport         boolean not null default false,   -- mobile viewport meta tag
  has_title            boolean not null default false,   -- <title> tag present
  has_meta_description boolean not null default false,   -- meta description present

  -- Raw issues list (for personalisation copy)
  issues               jsonb not null default '[]',

  -- Metadata
  audited_at           timestamptz not null default now(),
  error                text                               -- reason if audit failed
);

create index if not exists website_audits_company_id_idx
  on website_audits (company_id);

alter table website_audits enable row level security;
