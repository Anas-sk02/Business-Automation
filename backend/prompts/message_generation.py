"""Prompt construction for generating personalized, evidence-based WhatsApp outreach drafts."""

from typing import Any, Dict, List, Optional


def build_message_generation_prompt(
    lead: Dict[str, Any],
    campaign: Dict[str, Any],
    profile: Dict[str, Any],
    analysis: Optional[Dict[str, Any]] = None,
    verified_evidence: Optional[List[Dict[str, Any]]] = None,
    custom_instructions: Optional[str] = None,
) -> str:
    """Build structured prompt for AI to generate a high-converting, honest WhatsApp message.

    Per docs/decisions.md Section 7 & 10:
    - Only verified evidence items may be referenced.
    - No fabricated revenue, false urgency, or claims about lost customers.
    - Mandatory opt-out line: 'Reply STOP to opt out'.
    - Output must be strict JSON containing message_body, template_variables, and evidence_cited.

    Args:
        lead: Lead dictionary from database.
        campaign: Campaign dictionary containing service_offered and industry context.
        profile: User profile dictionary containing sender full_name and company_name.
        analysis: Optional AI analysis dictionary from Stage 4.
        verified_evidence: Strictly filtered list of evidence_items with verification_status='verified'.
        custom_instructions: Optional user-provided tone/offer guidance.

    Returns:
        Structured system/user prompt string formatted for AIClient.
    """
    def _clean(val: Any, max_len: int = 150) -> str:
        if not val:
            return ""
        s = str(val).strip().replace("\r", " ").replace("\n", " ")
        return s[:max_len]

    business_name = _clean(lead.get("business_name") or "Business Owner", 150)
    website_url = _clean(lead.get("website_url"), 250)
    location = _clean(lead.get("address") or lead.get("city") or campaign.get("location") or "your area", 150)
    industry = _clean(campaign.get("industry_label") or lead.get("category") or "local business", 100)
    service_offered = _clean(campaign.get("service_offered") or "Digital Growth & Web Solutions", 150)

    sender_name = _clean(profile.get("full_name") or "Business Specialist", 100)
    sender_company = _clean(profile.get("company_name") or "SignalForge Partner", 100)

    has_website = bool(website_url and website_url.strip())

    # Build evidence summary (sanitize descriptions to prevent prompt injection from crawled pages)
    evidence_lines: List[str] = []
    if verified_evidence:
        for idx, ev in enumerate(verified_evidence[:10], 1):
            title = _clean(ev.get("title") or ev.get("finding") or "Observed issue", 120)
            desc = _clean(ev.get("description") or ev.get("recommendation") or "", 300)
            evidence_lines.append(f"{idx}. {title}: {desc}")
    evidence_text = "\n".join(evidence_lines) if evidence_lines else "None (No website or clean baseline audit)"

    # Pitch angle from analysis
    pitch_angle = ""
    recommended_service = service_offered
    if analysis and isinstance(analysis, dict):
        pitch_angle = _clean(analysis.get("pitch_angle") or "", 200)
        rec = analysis.get("recommended_service")
        if rec:
            recommended_service = _clean(rec, 150)

    # Sanitize custom user instructions to max 1,000 characters
    custom_inst_clean = (
        str(custom_instructions).strip()[:1000].replace("```", "'''")
        if custom_instructions
        else ""
    )
    custom_instructions_block = (
        f"### USER CUSTOM INSTRUCTIONS:\n<user_guidance>\n{custom_inst_clean}\n</user_guidance>\n"
        if custom_inst_clean
        else ""
    )
    default_template_name = "business_website_intro" if has_website else "no_website_outreach"

    prompt = f"""You are an elite, highly professional B2B outreach copywriter for SignalForge AI.
Your job is to write a warm, respectful, concise WhatsApp outreach message from a digital service provider to a business owner.

### SENDER INFORMATION
- Sender Name: {sender_name}
- Sender Company: {sender_company}
- Service Offered: {service_offered} (Recommended Angle: {recommended_service})

### PROSPECT BUSINESS
- Business Name: {business_name}
- Industry / Niche: {industry}
- Location: {location}
- Website URL: {website_url if has_website else 'NO WEBSITE (Prospect currently operates without a website)'}
- Pitch Angle from Analysis: {pitch_angle or 'Help local business enhance their customer acquisition'}

### VERIFIED AUDIT EVIDENCE (USE ONLY THESE FACTS)
{evidence_text}

### MANDATORY OUTREACH GUIDELINES
1. **Fact-Based & Honest:**
   - Mention ONLY issues that appear in the VERIFIED AUDIT EVIDENCE list above.
   - If the business has NO website, focus respectfully on how a mobile-friendly site helps local customers find them.
   - NEVER claim lost revenue, specific lost customer numbers, or fabricated negative reviews.
   - NEVER use false urgency ("act now", "limited time offer").
2. **Formatting & Length:**
   - WhatsApp-native style: 3 to 4 short, readable paragraphs (around 70 to 120 words total).
   - Conversational, warm, and professional tone tailored to Indian SMB owners (no jargon).
   - Clear and soft Call to Action (e.g., "Would you be open to a quick 5-minute call or WhatsApp chat this week?").
3. **Mandatory Opt-Out:**
   - The very last line of the message body MUST be exactly:
     "Reply STOP to opt out"
4. **Template Variables for Fallback:**
   - Provide standard Twilio template variables matching:
     - Variable 1: recipient greeting (e.g. "there" or "Team {business_name}")
     - Variable 2: {business_name}
     - Variable 3: 1 short sentence summarizing the primary verified finding (e.g. "mobile layout issues making it hard for parents to read on phone")
     - Variable 4: {sender_name}
     - Variable 5: {sender_company}

{custom_instructions_block}

### OUTPUT SPECIFICATION
You MUST respond with a single valid JSON object with NO surrounding markdown or backticks.
The JSON must adhere to this exact schema:
{{
  "message_body": "Full personalized WhatsApp message text with line breaks and the final 'Reply STOP to opt out' line.",
  "template_name": "{default_template_name}",
  "template_variables": {{
    "1": "there",
    "2": "{business_name}",
    "3": "primary specific verified issue summary",
    "4": "{sender_name}",
    "5": "{sender_company}"
  }},
  "evidence_cited": ["Brief title of verified finding(s) referenced"]
}}"""

    return prompt
