"""
Tests for the production readiness gate.
All DNS and HTTP calls are mocked — no real network requests made.
DRY_RUN remains true throughout.
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def minimal_env(**overrides):
    """Returns an env dict with all mandatory gates satisfied (except DRY_RUN)."""
    base = {
        "BMS_COMPANY_NUMBER":       "12345678",
        "BMS_REGISTERED_ADDRESS":   "1 Test St, London, EC1A 1BB",
        "UNSUBSCRIBE_URL":          "https://bemysocial.co.uk/unsubscribe",
        "MILLION_VERIFIER_API_KEY": "mv_test_key",
        "SMARTLEAD_API_KEY":        "sl_test_key",
        "ANTHROPIC_API_KEY":        "sk-ant-test",
        "DRY_RUN":                  "true",   # Always true in tests
        "EMAIL_WARMUP_COMPLETED":   "false",
        "LIA_APPROVED":             "false",
        "PRIVACY_NOTICE_CONFIRMED": "false",
        "SENDING_DOMAIN":           "",       # No domain → DNS checks skipped
    }
    base.update(overrides)
    return base


# ─────────────────────────────────────────────────────────────
# Basic structure
# ─────────────────────────────────────────────────────────────

@patch.dict(os.environ, minimal_env(), clear=True)
def test_returns_required_keys():
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert "ready_for_live_sending" in result
    assert "checks" in result
    assert "blockers" in result
    assert "dry_run_active" in result


@patch.dict(os.environ, minimal_env(), clear=True)
def test_dry_run_active_by_default():
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["dry_run_active"] is True


@patch.dict(os.environ, minimal_env(), clear=True)
def test_not_ready_when_dry_run_true():
    """ready_for_live_sending must be False when DRY_RUN=true regardless of other gates."""
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["ready_for_live_sending"] is False


# ─────────────────────────────────────────────────────────────
# Individual gate checks
# ─────────────────────────────────────────────────────────────

@patch.dict(os.environ, minimal_env(MILLION_VERIFIER_API_KEY=""), clear=True)
def test_missing_mv_key_is_not_configured():
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["millionverifier"]["status"] == "NOT_CONFIGURED"
    assert any("millionverifier" in b for b in result["blockers"])


@patch.dict(os.environ, minimal_env(MILLION_VERIFIER_API_KEY="real_key"), clear=True)
def test_mv_key_present_is_ready():
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["millionverifier"]["status"] == "READY"


@patch.dict(os.environ, minimal_env(SMARTLEAD_API_KEY="", SMTP_HOST=""), clear=True)
def test_missing_sending_platform_is_not_configured():
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["sending_platform"]["status"] == "NOT_CONFIGURED"
    assert any("sending_platform" in b for b in result["blockers"])


@patch.dict(os.environ, minimal_env(EMAIL_WARMUP_COMPLETED="false"), clear=True)
def test_warmup_not_complete_is_business_action():
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["warmup"]["status"] == "BUSINESS_ACTION_REQUIRED"
    assert result["checks"]["warmup"]["can_claude_verify"] is False


@patch.dict(os.environ, minimal_env(EMAIL_WARMUP_COMPLETED="true"), clear=True)
def test_warmup_confirmed_is_ready():
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["warmup"]["status"] == "READY"


@patch.dict(os.environ, minimal_env(LIA_APPROVED="false"), clear=True)
def test_lia_not_approved_is_business_action():
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["lia"]["status"] == "BUSINESS_ACTION_REQUIRED"
    assert result["checks"]["lia"]["can_claude_verify"] is False


@patch.dict(os.environ, minimal_env(LIA_APPROVED="true"), clear=True)
def test_lia_approved_is_ready():
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["lia"]["status"] == "READY"


@patch.dict(os.environ, minimal_env(PRIVACY_NOTICE_CONFIRMED="false"), clear=True)
def test_privacy_not_confirmed_is_business_action():
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["privacy_notice"]["status"] == "BUSINESS_ACTION_REQUIRED"


@patch.dict(os.environ, minimal_env(PRIVACY_NOTICE_CONFIRMED="true"), clear=True)
def test_privacy_confirmed_is_ready():
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["privacy_notice"]["status"] == "READY"


# ─────────────────────────────────────────────────────────────
# DNS checks
# ─────────────────────────────────────────────────────────────

@patch.dict(os.environ, minimal_env(SENDING_DOMAIN=""), clear=True)
def test_no_sending_domain_gives_not_configured_dns():
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["spf"]["status"]   == "NOT_CONFIGURED"
    assert result["checks"]["dkim"]["status"]  == "NOT_CONFIGURED"
    assert result["checks"]["dmarc"]["status"] == "NOT_CONFIGURED"


@patch.dict(os.environ, minimal_env(SENDING_DOMAIN="bemysocial.co.uk"), clear=True)
@patch("dns.resolver.resolve")
def test_spf_found_is_ready(mock_resolve):
    mock_rdata = MagicMock()
    mock_rdata.strings = [b"v=spf1 include:spf.smartlead.ai ~all"]
    mock_resolve.return_value = [mock_rdata]
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["spf"]["status"] == "READY"


@patch.dict(os.environ, minimal_env(SENDING_DOMAIN="bemysocial.co.uk"), clear=True)
@patch("dns.resolver.resolve")
def test_no_spf_is_technical_action(mock_resolve):
    import dns.resolver as dnsmod
    mock_resolve.side_effect = dnsmod.NXDOMAIN()
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["spf"]["status"] == "TECHNICAL_ACTION_REQUIRED"


@patch.dict(os.environ, minimal_env(SENDING_DOMAIN="bemysocial.co.uk", DKIM_SELECTOR="s1"), clear=True)
@patch("dns.resolver.resolve")
def test_dkim_found_is_ready(mock_resolve):
    mock_rdata = MagicMock()
    mock_rdata.strings = [b"v=DKIM1; p=MIGfMA0G..."]
    mock_resolve.return_value = [mock_rdata]
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    # dkim check
    assert result["checks"]["dkim"]["status"] == "READY"


@patch.dict(os.environ, minimal_env(SENDING_DOMAIN="bemysocial.co.uk"), clear=True)
@patch("dns.resolver.resolve")
def test_dmarc_found_is_ready(mock_resolve):
    mock_rdata = MagicMock()
    mock_rdata.strings = [b"v=DMARC1; p=none; rua=mailto:dmarc@bemysocial.co.uk"]
    mock_resolve.return_value = [mock_rdata]
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["dmarc"]["status"] == "READY"


# ─────────────────────────────────────────────────────────────
# require_production_ready gate
# ─────────────────────────────────────────────────────────────

@patch.dict(os.environ, minimal_env(), clear=True)
def test_gate_passes_in_dry_run():
    """require_production_ready must NOT raise when dry_run=True."""
    import importlib, production_readiness
    importlib.reload(production_readiness)
    # Should not raise
    production_readiness.require_production_ready(dry_run=True)


@patch.dict(os.environ, minimal_env(DRY_RUN="false"), clear=True)
def test_gate_blocks_live_send_when_not_ready():
    """require_production_ready must raise ProductionNotReadyError for live sends that aren't ready."""
    import importlib, production_readiness
    importlib.reload(production_readiness)
    with pytest.raises(production_readiness.ProductionNotReadyError):
        production_readiness.require_production_ready(dry_run=False)


@patch.dict(os.environ, minimal_env(
    DRY_RUN="false",
    EMAIL_WARMUP_COMPLETED="true",
    LIA_APPROVED="true",
    PRIVACY_NOTICE_CONFIRMED="true",
    SENDING_DOMAIN="bemysocial.co.uk",
), clear=True)
@patch("dns.resolver.resolve")
def test_gate_passes_when_all_mandatory_ready(mock_resolve):
    """Gate passes when all mandatory gates are READY and DRY_RUN=false."""
    mock_rdata = MagicMock()
    # SPF, DKIM, DMARC all return valid records
    def resolve_side(host, rtype, **kw):
        if "_dmarc" in host:
            r = MagicMock(); r.strings = [b"v=DMARC1; p=none"]; return [r]
        if "_domainkey" in host:
            r = MagicMock(); r.strings = [b"v=DKIM1; p=abc123"]; return [r]
        r = MagicMock(); r.strings = [b"v=spf1 include:spf.smartlead.ai ~all"]; return [r]
    mock_resolve.side_effect = resolve_side

    import importlib, production_readiness
    importlib.reload(production_readiness)
    # Should not raise
    production_readiness.require_production_ready(dry_run=False)


# ─────────────────────────────────────────────────────────────
# Anthropic is optional (non-mandatory)
# ─────────────────────────────────────────────────────────────

@patch.dict(os.environ, minimal_env(ANTHROPIC_API_KEY=""), clear=True)
def test_missing_anthropic_is_not_a_blocker():
    """Anthropic key is optional — its absence must NOT appear in blockers."""
    import importlib, production_readiness
    importlib.reload(production_readiness)
    result = production_readiness.check_production_readiness()
    assert result["checks"]["anthropic"]["status"] == "NOT_CONFIGURED"
    # Must NOT be in blockers list (it's non-mandatory)
    assert not any("anthropic" in b for b in result["blockers"])
