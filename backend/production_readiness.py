"""
BMS LeadFlow — Production Readiness Gate
=========================================
Checks every requirement that must be satisfied before a real cold email
can be sent.  Called:
  • GET  /api/production-readiness   (returns the full status dict)
  • Inside send_campaign_email()     (blocks if DRY_RUN=false + not ready)
  • Inside process_due_follow_ups()  (same)

IMPORTANT
---------
* DRY_RUN defaults to TRUE. This module never changes that default.
* Manual flags (warmup, LIA, privacy notice) are read from environment
  variables that must be set explicitly by a human operator.
* DNS checks use real DNS queries — they never fabricate results.
* A check can only become READY when real, verifiable evidence exists.
"""

import os
import logging
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# ── Status constants ─────────────────────────────────────────
READY             = "READY"
NOT_CONFIGURED    = "NOT_CONFIGURED"
BUSINESS_ACTION   = "BUSINESS_ACTION_REQUIRED"
TECHNICAL_ACTION  = "TECHNICAL_ACTION_REQUIRED"
BLOCKED           = "BLOCKED"

# ── Environment reading ──────────────────────────────────────
_TRUE_VALUES = {"true", "1", "yes"}

def _env_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower().strip() in _TRUE_VALUES

def _env_str(key: str) -> str:
    return (os.getenv(key) or "").strip()


# ─────────────────────────────────────────────────────────────
# DNS helpers (real queries — never fabricated)
# ─────────────────────────────────────────────────────────────

def _check_spf(domain: str) -> tuple[bool, str]:
    """Return (found: bool, detail: str) for SPF TXT record on domain."""
    if not domain:
        return False, "No sending domain configured (SENDING_DOMAIN env var not set)"
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "TXT", lifetime=5)
        for rdata in answers:
            txt = b"".join(rdata.strings).decode("utf-8", errors="replace")
            if txt.startswith("v=spf1"):
                return True, f"SPF record found: {txt[:120]}"
        return False, f"No SPF TXT record found on {domain}"
    except ImportError:
        return False, "dnspython not installed — cannot verify SPF"
    except Exception as exc:
        return False, f"DNS lookup failed: {exc}"


def _check_dkim(domain: str, selector: str = "") -> tuple[bool, str]:
    """
    Check for DKIM public key record.
    Tries the configured selector first, then common defaults.
    """
    if not domain:
        return False, "No sending domain configured"
    selectors = [s for s in [selector, "default", "google", "s1", "s2", "mail", "key1"] if s]
    try:
        import dns.resolver
        for sel in selectors:
            host = f"{sel}._domainkey.{domain}"
            try:
                answers = dns.resolver.resolve(host, "TXT", lifetime=5)
                for rdata in answers:
                    txt = b"".join(rdata.strings).decode("utf-8", errors="replace")
                    if "v=DKIM1" in txt or "p=" in txt:
                        return True, f"DKIM record found at {host}"
            except Exception:
                continue
        return False, f"No DKIM TXT record found on {domain} (tried selectors: {', '.join(selectors)})"
    except ImportError:
        return False, "dnspython not installed — cannot verify DKIM"


def _check_dmarc(domain: str) -> tuple[bool, str]:
    """Check for DMARC policy record."""
    if not domain:
        return False, "No sending domain configured"
    try:
        import dns.resolver
        host = f"_dmarc.{domain}"
        answers = dns.resolver.resolve(host, "TXT", lifetime=5)
        for rdata in answers:
            txt = b"".join(rdata.strings).decode("utf-8", errors="replace")
            if txt.startswith("v=DMARC1"):
                return True, f"DMARC record found: {txt[:120]}"
        return False, f"No DMARC record found at {host}"
    except ImportError:
        return False, "dnspython not installed — cannot verify DMARC"
    except Exception as exc:
        return False, f"DNS lookup failed: {exc}"


# ─────────────────────────────────────────────────────────────
# Sending platform auth probe (no email sent)
# ─────────────────────────────────────────────────────────────

def _check_smartlead_auth(api_key: str) -> tuple[bool, str]:
    """
    Probe Smartlead's /email-accounts endpoint to verify credentials.
    Does NOT send any email.
    """
    if not api_key:
        return False, "SMARTLEAD_API_KEY is not set"
    try:
        import requests
        resp = requests.get(
            "https://server.smartlead.ai/api/v1/email-accounts",
            params={"api_key": api_key},
            timeout=8,
        )
        if resp.status_code == 200:
            accounts = resp.json() if isinstance(resp.json(), list) else []
            return True, f"Authenticated — {len(accounts)} email account(s) found"
        if resp.status_code == 401:
            return False, "Smartlead rejected the API key (401 Unauthorized)"
        return False, f"Smartlead returned HTTP {resp.status_code}"
    except Exception as exc:
        return False, f"Could not reach Smartlead API: {exc}"


# ─────────────────────────────────────────────────────────────
# Main readiness check
# ─────────────────────────────────────────────────────────────

def check_production_readiness(probe_sending_platform: bool = False) -> dict:
    """
    Run all 11 production readiness checks.

    Returns:
        {
          "ready_for_live_sending": bool,
          "checks": {<id>: {"status": str, "detail": str, ...}},
          "blockers": [str, ...],
        }

    DRY_RUN is never modified by this function.
    Manual flags are read from env vars and cannot be faked by code.
    DNS checks use real queries and are never fabricated.
    """

    checks   = {}
    blockers = []

    # ── Helper ───────────────────────────────────────────────
    def add(check_id: str, status: str, label: str, detail: str,
            who: str, can_claude_verify: bool, action: str = "",
            mandatory: bool = True):
        checks[check_id] = {
            "status":            status,
            "label":             label,
            "detail":            detail,
            "action_required":   action,
            "who_must_act":      who,
            "can_claude_verify": can_claude_verify,
            "mandatory":         mandatory,
        }
        if mandatory and status != READY:
            blockers.append(f"[{check_id}] {detail}")

    # ── 1. PECR / UK GDPR — structural check ─────────────────
    pecr_ok = (
        bool(_env_str("BMS_COMPANY_NUMBER")) and
        bool(_env_str("BMS_REGISTERED_ADDRESS")) and
        bool(_env_str("BMS_UNSUBSCRIBE_BASE_URL") or _env_str("UNSUBSCRIBE_URL"))
    )
    add(
        "pecr_structural",
        READY if pecr_ok else NOT_CONFIGURED,
        "PECR structural config (company number, address, unsubscribe URL)",
        "All set — BMS_COMPANY_NUMBER, BMS_REGISTERED_ADDRESS, unsubscribe URL present" if pecr_ok
            else "Missing BMS_COMPANY_NUMBER and/or BMS_REGISTERED_ADDRESS and/or unsubscribe URL in .env",
        action="Set BMS_COMPANY_NUMBER, BMS_REGISTERED_ADDRESS, BMS_UNSUBSCRIBE_BASE_URL in backend/.env",
        who="Technical (James / Prashanth)",
        can_claude_verify=True,
    )

    # ── 2. MillionVerifier API key ────────────────────────────
    mv_key = _env_str("MILLION_VERIFIER_API_KEY")
    add(
        "millionverifier",
        READY if mv_key else NOT_CONFIGURED,
        "MillionVerifier API key",
        f"Key present ({mv_key[:6]}...)" if mv_key else "MILLION_VERIFIER_API_KEY is not set — email verification disabled",
        action="Set MILLION_VERIFIER_API_KEY in backend/.env (get key at app.millionverifier.com)",
        who="Technical (James)",
        can_claude_verify=True,
    )

    # ── 3. Sending platform ───────────────────────────────────
    sl_key    = _env_str("SMARTLEAD_API_KEY")
    smtp_host = _env_str("SMTP_HOST")
    platform_configured = bool(sl_key or smtp_host)

    if not platform_configured:
        add(
            "sending_platform",
            NOT_CONFIGURED,
            "Sending platform (Smartlead or SMTP)",
            "Neither SMARTLEAD_API_KEY nor SMTP_HOST is set",
            action="Set SMARTLEAD_API_KEY in backend/.env (get key at app.smartlead.ai → Settings → API Keys)",
            who="Technical (James)",
            can_claude_verify=True,
        )
    elif probe_sending_platform and sl_key:
        auth_ok, auth_detail = _check_smartlead_auth(sl_key)
        add(
            "sending_platform",
            READY if auth_ok else TECHNICAL_ACTION,
            "Sending platform — Smartlead authentication verified",
            auth_detail,
            action="" if auth_ok else "Check SMARTLEAD_API_KEY is correct and account is active",
            who="Technical (James)",
            can_claude_verify=True,
        )
    else:
        platform_label = "Smartlead" if sl_key else "SMTP"
        add(
            "sending_platform",
            READY,
            f"Sending platform configured ({platform_label} credentials present)",
            f"{platform_label} credentials are present in .env (not probed — set probe_sending_platform=True to verify auth)",
            who="N/A",
            can_claude_verify=False,
        )

    # ── 4. DRY_RUN status ────────────────────────────────────
    dry_run_active = _env_bool("DRY_RUN", default=True)
    add(
        "dry_run_disabled",
        BLOCKED if dry_run_active else READY,
        "DRY_RUN disabled for live sending",
        "DRY_RUN=true — all sends are simulated, no real emails will be sent"
            if dry_run_active
            else "DRY_RUN=false — live sending mode is active",
        action="Set DRY_RUN=false in backend/.env ONLY after all other gates are READY",
        who="Technical (James — deliberate human action required)",
        can_claude_verify=True,
    )

    # ── 5. Anthropic API key ──────────────────────────────────
    anthropic_key = _env_str("ANTHROPIC_API_KEY")
    add(
        "anthropic",
        READY if anthropic_key else NOT_CONFIGURED,
        "Anthropic API key (Claude AI personalisation)",
        f"Key present ({anthropic_key[:8]}...)" if anthropic_key
            else "ANTHROPIC_API_KEY not set — Claude personalisation disabled, rule-based fallback will be used",
        action="Set ANTHROPIC_API_KEY in backend/.env (get key at console.anthropic.com)",
        who="Technical (James)",
        can_claude_verify=True,
        mandatory=False,   # Not mandatory — rule-based fallback works
    )

    # ── 6. Email warmup ───────────────────────────────────────
    warmup_done = _env_bool("EMAIL_WARMUP_COMPLETED", default=False)
    add(
        "warmup",
        READY if warmup_done else BUSINESS_ACTION,
        "Email inbox warmup completed",
        "EMAIL_WARMUP_COMPLETED=true — warmup confirmed by operator"
            if warmup_done
            else "EMAIL_WARMUP_COMPLETED is not set to 'true'. Warmup must be confirmed manually after 6–8 weeks of warmup at 20 emails/day.",
        action="Run Smartlead warmup for 6–8 weeks. Once complete, set EMAIL_WARMUP_COMPLETED=true in backend/.env",
        who="Business (James — cannot be done by Claude)",
        can_claude_verify=False,
    )

    # ── 7. LIA approval ──────────────────────────────────────
    lia_approved = _env_bool("LIA_APPROVED", default=False)
    add(
        "lia",
        READY if lia_approved else BUSINESS_ACTION,
        "Legitimate Interest Assessment (LIA) approved",
        "LIA_APPROVED=true — approved by legal team"
            if lia_approved
            else "LIA_APPROVED is not set to 'true'. A Legitimate Interests Assessment document must be completed and signed off by James and/or BMS legal team before PECR-compliant cold outreach can begin.",
        action="Complete the LIA document with legal adviser. Once signed off, set LIA_APPROVED=true in backend/.env",
        who="Business/Legal (James + legal adviser — cannot be done by Claude)",
        can_claude_verify=False,
    )

    # ── 8. Privacy notice ────────────────────────────────────
    privacy_confirmed = _env_bool("PRIVACY_NOTICE_CONFIRMED", default=False)
    add(
        "privacy_notice",
        READY if privacy_confirmed else BUSINESS_ACTION,
        "Privacy notice published",
        "PRIVACY_NOTICE_CONFIRMED=true — privacy notice confirmed as live"
            if privacy_confirmed
            else "PRIVACY_NOTICE_CONFIRMED is not set to 'true'. A GDPR-compliant privacy notice must be published on bemysocial.co.uk before outreach begins.",
        action="Publish privacy notice at https://bemysocial.co.uk/privacy. Then set PRIVACY_NOTICE_CONFIRMED=true in backend/.env",
        who="Business (James + web team — cannot be done by Claude)",
        can_claude_verify=False,
    )

    # ── 9–11. DNS checks (SPF / DKIM / DMARC) ────────────────
    sending_domain = _env_str("SENDING_DOMAIN") or _env_str("SMARTLEAD_SENDING_DOMAIN")
    dkim_selector  = _env_str("DKIM_SELECTOR")  # e.g. "s1", "google", "default"

    spf_ok,   spf_detail   = _check_spf(sending_domain)
    dkim_ok,  dkim_detail  = _check_dkim(sending_domain, selector=dkim_selector)
    dmarc_ok, dmarc_detail = _check_dmarc(sending_domain)

    if not sending_domain:
        dns_not_configured = "SENDING_DOMAIN env var not set — cannot run DNS checks"
        for dns_id, dns_label in [
            ("spf",   "SPF record on sending domain"),
            ("dkim",  "DKIM record on sending domain"),
            ("dmarc", "DMARC policy on sending domain"),
        ]:
            add(dns_id, NOT_CONFIGURED, dns_label, dns_not_configured,
                action="Set SENDING_DOMAIN=yourdomain.com in backend/.env, then re-run this check",
                who="Technical (James)", can_claude_verify=True)
    else:
        add(
            "spf",
            READY if spf_ok else TECHNICAL_ACTION,
            f"SPF record on {sending_domain}",
            spf_detail,
            action="" if spf_ok else f"Add a TXT record to {sending_domain}: v=spf1 include:spf.smartlead.ai ~all",
            who="Technical (domain registrar / DNS admin)",
            can_claude_verify=True,
        )
        add(
            "dkim",
            READY if dkim_ok else TECHNICAL_ACTION,
            f"DKIM record on {sending_domain}",
            dkim_detail,
            action="" if dkim_ok else "Add the DKIM TXT record provided by Smartlead to your DNS (selector._domainkey.yourdomain.com)",
            who="Technical (domain registrar / DNS admin)",
            can_claude_verify=True,
        )
        add(
            "dmarc",
            READY if dmarc_ok else TECHNICAL_ACTION,
            f"DMARC policy on {sending_domain}",
            dmarc_detail,
            action="" if dmarc_ok else f"Add a TXT record: _dmarc.{sending_domain} → v=DMARC1; p=none; rua=mailto:dmarc@{sending_domain}",
            who="Technical (domain registrar / DNS admin)",
            can_claude_verify=True,
        )

    # ── ready_for_live_sending ────────────────────────────────
    # ALL mandatory gates must be READY, AND DRY_RUN must be false
    mandatory_ids     = [k for k, v in checks.items() if v.get("mandatory", True)]
    all_mandatory_ok  = all(checks[k]["status"] == READY for k in mandatory_ids)
    ready_for_live    = all_mandatory_ok and not dry_run_active

    return {
        "ready_for_live_sending": ready_for_live,
        "dry_run_active":         dry_run_active,
        "sending_domain":         sending_domain or None,
        "checks":                 checks,
        "blockers":               blockers,
        "note": (
            "DRY_RUN is still active — no real emails can be sent regardless of gate status"
            if dry_run_active else
            "DRY_RUN is disabled — live sending will occur if you trigger a send"
        ),
    }


# ─────────────────────────────────────────────────────────────
# Production gate (raises if live send attempted without passing)
# ─────────────────────────────────────────────────────────────

class ProductionNotReadyError(Exception):
    """Raised when a live send is attempted before all gates pass."""


def require_production_ready(dry_run: bool) -> None:
    """
    Call this at the start of every real-send code path.
    In dry-run mode: passes immediately (no gate needed).
    In live mode:    raises ProductionNotReadyError if any mandatory gate fails.
    """
    if dry_run:
        return  # Dry run — gate not required

    status = check_production_readiness()
    if not status["ready_for_live_sending"]:
        raise ProductionNotReadyError(
            "Live sending is BLOCKED. Failing requirements:\n" +
            "\n".join(f"  • {b}" for b in status["blockers"])
        )
