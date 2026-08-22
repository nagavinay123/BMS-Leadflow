"""
BMS LeadFlow — Email Template Generator
Week 8 / Week 9

Generates personalised cold outreach emails for BMS sales team.
Each email is tailored using:
  - Company name + owner first name
  - Real website audit findings (mobile score, SSL, PageSpeed)
  - Business type / sector
  - Google rating and review count

The emails are honest, specific, and reference actual problems found —
not generic "we can help your business" spam.

Week 9 upgrade: swap _build_body() with Claude API call for AI-written copy.
"""


def generate_email(company: dict, sender_name: str = "James", sender_title: str = "Director") -> dict:
    """
    Generate a personalised outreach email for a company.

    Args:
        company: full company dict (from get_companies_with_audits)
        sender_name: BMS sender name shown in the email sign-off

    Returns:
        {"subject": str, "body": str, "template_used": str}
    """
    first_name  = company.get("contact_first_name") or company.get("contact_full_name", "").split()[0]
    greeting    = f"Hi {first_name}," if first_name else "Hi there,"
    biz_name    = company.get("name", "your business")
    issues      = company.get("issues") or []
    has_email   = bool(company.get("contact_email"))
    perf        = company.get("performance_score")
    mobile      = company.get("mobile_score")
    has_ssl     = company.get("https")
    has_website = company.get("has_website")
    rating      = company.get("rating")
    reviews     = company.get("review_count") or 0

    subject = _build_subject(biz_name, issues, has_website)
    body    = _build_body(
        greeting, biz_name, issues, perf, mobile, has_ssl,
        rating, reviews, sender_name, sender_title
    )

    return {
        "subject":       subject,
        "body":          body,
        "template_used": "audit_personalised_v1",
    }


# ──────────────────────────────────────────────
# Subject line builder
# ──────────────────────────────────────────────

def _build_subject(biz_name: str, issues: list, has_website: bool) -> str:
    issue_types = [i.get("type") for i in issues]

    if not has_website:
        return f"Quick question about {biz_name}'s online presence"
    if "no_ssl" in issue_types:
        return f"Your website is flagged as 'Not Secure' — quick fix available"
    if "poor_mobile" in issue_types or "poor_performance" in issue_types:
        return f"Your website is losing customers on mobile — here's why"
    if "slow_mobile" in issue_types or "slow_desktop" in issue_types:
        return f"One thing holding {biz_name} back from more Google enquiries"
    if issues:
        return f"A few things we noticed about {biz_name}'s website"
    return f"Helping {biz_name} get more customers from Google"


# ──────────────────────────────────────────────
# Body builder
# ──────────────────────────────────────────────

def _build_body(
    greeting, biz_name, issues, perf, mobile, has_ssl,
    rating, reviews, sender_name, sender_title
) -> str:

    issue_types = [i.get("type") for i in issues]
    paras       = []

    # ── Opening ─────────────────────────────────────────────
    paras.append(greeting)
    paras.append("")

    if issues:
        paras.append(
            f"I came across {biz_name} while researching businesses in your area, "
            f"and I noticed a few things on your website that might be costing you customers online."
        )
    else:
        paras.append(
            f"I came across {biz_name} while researching local businesses and wanted to reach out."
        )

    paras.append("")

    # ── Specific audit findings ──────────────────────────────
    findings = []

    if "no_ssl" in issue_types:
        findings.append(
            "🔒 Your website doesn't have an SSL certificate, which means Google "
            "labels it as \"Not Secure\" — this puts off customers before they've even read a word."
        )

    if perf is not None and perf < 50:
        findings.append(
            f"⚡ Your desktop speed score is {perf}/100. Google uses page speed as a ranking "
            f"factor, so a slow site means fewer enquiries from search."
        )
    elif perf is not None and perf < 70:
        findings.append(
            f"⚡ Your website scores {perf}/100 on desktop speed — there's room to improve, "
            f"which would help your Google ranking."
        )

    if mobile is not None and mobile < 50:
        findings.append(
            f"📱 Your mobile speed score is only {mobile}/100. Most of your customers are "
            f"searching on their phones, so this is likely costing you leads every day."
        )
    elif mobile is not None and mobile < 70:
        findings.append(
            f"📱 Your site scores {mobile}/100 on mobile — most searches happen on phones, "
            f"so improving this would directly increase enquiries."
        )

    if "no_viewport" in issue_types:
        findings.append(
            "📐 Your website isn't optimised for mobile screens. Visitors on phones "
            "have to pinch-zoom to read anything, which means most will leave immediately."
        )

    if "no_meta_desc" in issue_types or "no_title" in issue_types:
        findings.append(
            "🔍 Your website is missing basic SEO elements (title/description tags) "
            "that tell Google what your business does — this reduces how often you appear in searches."
        )

    if findings:
        paras.append("Here's what we found:")
        paras.append("")
        for f in findings:
            paras.append(f)
        paras.append("")

    # ── Social proof mention (if they have reviews) ──────────
    if rating and reviews >= 10:
        paras.append(
            f"You've clearly built a great reputation — {reviews} Google reviews at {rating}⭐ "
            f"is impressive. The goal would be to make sure your website matches the quality of your service "
            f"and converts those searchers into paying customers."
        )
        paras.append("")

    # ── BMS offer ───────────────────────────────────────────
    paras.append(
        "At BeMySocial, we specialise in helping local businesses fix exactly these issues. "
        "We've worked with businesses across the UK to improve their Google rankings, "
        "mobile performance and online presence — typically seeing a measurable increase "
        "in enquiries within 90 days."
    )
    paras.append("")

    # ── CTA ─────────────────────────────────────────────────
    paras.append(
        "Would you be open to a free, no-obligation 15-minute call this week? "
        "I can walk through exactly what we'd do and what results you could realistically expect."
    )
    paras.append("")

    # ── Sign-off ─────────────────────────────────────────────
    paras.append(f"Best regards,")
    paras.append(f"{sender_name}")
    paras.append(f"{sender_title}, BeMySocial")
    paras.append("📞 | 🌐 bemysocial.co.uk")
    paras.append("")
    paras.append(
        "P.S. I can send over a free full audit report for your website if that would be useful — "
        "just reply to this email."
    )
    paras.append("")
    paras.append("─" * 60)
    paras.append(
        "This email was sent because we believe we can genuinely help your business. "
        "If you'd prefer not to hear from us, just reply with 'unsubscribe' and we'll remove you immediately."
    )

    return "\n".join(paras)


# ──────────────────────────────────────────────
# Follow-up email generator (Steps 2 + 3)
# ──────────────────────────────────────────────

def generate_followup_email(company: dict, step: int = 2, sender_name: str = "James") -> dict:
    """
    Generate a follow-up email for a company (step 2 or 3 in the sequence).
    Steps are shorter, reference the original email, and have a different CTA.
    """
    biz_name   = company.get("name", "your business")
    first_name = company.get("contact_first_name") or (company.get("contact_full_name") or "").split()[0]
    greeting   = f"Hi {first_name}," if first_name else "Hi there,"

    if step == 2:
        subject = f"Re: A few things we noticed about {biz_name}"
        body    = "\n".join([
            greeting,
            "",
            "Just following up on my email from a few days ago — I wanted to make sure it didn't get lost.",
            "",
            f"We noticed a few things on {biz_name}'s website that are likely costing you customers "
            f"— I'd love to walk you through them on a quick 15-minute call.",
            "",
            "There's no obligation at all — just a short, practical conversation about what we found and what's possible.",
            "",
            "Does this week or next work for you?",
            "",
            f"Best,",
            f"{sender_name}",
            "BeMySocial | bemysocial.co.uk",
        ])
    else:
        subject = f"Last note re: {biz_name}'s online presence"
        body    = "\n".join([
            greeting,
            "",
            "I'll keep this short — this will be my final email.",
            "",
            f"We carried out a quick audit of {biz_name}'s website and found a few things that "
            f"could genuinely affect how many customers find you online.",
            "",
            "If you'd like to see the results and get some free advice on what to improve, "
            "just hit reply and say 'yes' — takes 15 minutes.",
            "",
            "If now's not the right time, no worries at all — I wish you every success.",
            "",
            f"Best,",
            f"{sender_name}",
            "BeMySocial | bemysocial.co.uk",
        ])

    return {
        "subject":       subject,
        "body":          body,
        "template_used": f"follow_up_step_{step}_v1",
    }


# ──────────────────────────────────────────────
# Batch generate for a list of companies
# ──────────────────────────────────────────────

def generate_batch(companies: list, sender_name: str = "James") -> list:
    """
    Generate email drafts for a list of companies.
    Returns list of (company_id, draft_dict) tuples.
    """
    results = []
    for company in companies:
        if not company.get("id"):
            continue
        draft = generate_email(company, sender_name=sender_name)
        results.append((company["id"], draft))
    return results


# ──────────────────────────────────────────────
# CLI test
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # Test with a dummy company
    test_company = {
        "id":                  "test-123",
        "name":                "Smith's Plumbing Ltd",
        "contact_first_name":  "John",
        "contact_last_name":   "Smith",
        "has_website":         True,
        "rating":              4.6,
        "review_count":        47,
        "performance_score":   38,
        "mobile_score":        29,
        "https":               False,
        "issues": [
            {"type": "no_ssl",        "label": "No HTTPS / SSL certificate"},
            {"type": "poor_performance", "label": "Desktop speed score only 38/100"},
            {"type": "poor_mobile",   "label": "Mobile speed score only 29/100"},
            {"type": "no_meta_desc",  "label": "Missing meta description"},
        ],
    }

    draft = generate_email(test_company)
    print(f"SUBJECT: {draft['subject']}\n")
    print(draft["body"])
