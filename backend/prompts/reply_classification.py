"""Reply Classification Prompt for Stage 5: WhatsApp Outreach & Reply Tracking.

Constructs structured AI prompts to classify inbound WhatsApp messages into the 9 canonical
pipeline categories defined in docs/decisions.md Section 5 and docs/prompts.md Section 2.
"""

from typing import Optional


def build_reply_classification_prompt(
    business_name: str,
    service_offered: str,
    reply_text: str,
    last_outreach_summary: Optional[str] = None,
) -> str:
    """Build structured prompt for AI to classify an incoming prospect WhatsApp reply.

    Args:
        business_name: Prospect business name.
        service_offered: Service pitched in our campaign.
        reply_text: Untrusted incoming prospect message body.
        last_outreach_summary: Optional brief summary of our last sent message.

    Returns:
        Structured system/user prompt string formatted for AIClient.
    """
    clean_biz = str(business_name).strip()[:150] or "Business Owner"
    clean_service = str(service_offered).strip()[:150] or "Digital & Web Solutions"
    clean_outreach = str(last_outreach_summary).strip()[:300] if last_outreach_summary else "Outreach regarding digital web solutions"
    # Sanitize untrusted reply text to prevent prompt injection
    clean_reply = str(reply_text).strip()[:1000].replace("```", "'''")

    prompt = f"""You are an expert sales reply classifier for SignalForge AI.
Analyze the following WhatsApp reply from a local business lead and classify it into exactly one category.

### CONTEXT
- Prospect Business: {clean_biz}
- Service Pitched: {clean_service}
- Our Last Message Summary: {clean_outreach}

### INCOMING PROSPECT REPLY
<prospect_reply>
{clean_reply}
</prospect_reply>

### ALLOWED CATEGORIES (CHOOSE EXACTLY ONE)
1. "interested" — Lead expresses interest, wants to know more, or agrees to connect.
   Examples: "Yes tell me more", "I'm interested", "Sure, let's discuss", "Sounds good", "Haan batao"
2. "wants_info" — Lead asks for general information, details, or portfolio.
   Examples: "What exactly do you offer?", "Send me details", "What does this include?"
3. "pricing_request" — Lead specifically asks about pricing, cost, packages, or rates.
   Examples: "What's the cost?", "Send pricing", "How much do you charge?", "Kitna charges hoga?"
4. "meeting_request" — Lead asks to schedule a phone call, Zoom meeting, or visit.
   Examples: "Let's meet tomorrow", "Can we talk on call?", "When are you free?", "Call me at 4pm"
5. "not_interested" — Lead declines the offer politely or directly.
   Examples: "Not interested", "No thanks", "We don't need this", "Nahi chahiye"
6. "not_now" — Lead is busy or asks to follow up at a later time.
   Examples: "Busy right now", "Contact next month", "Travelling, msg later", "Abhi time nahi hai"
7. "wrong_number" — Reply indicates wrong number, wrong business, or person moved.
   Examples: "Wrong number", "Who is this?", "I don't own this clinic", "Wrong person"
8. "opt_out" — Lead explicitly demands to stop messaging or be removed from list.
   Examples: "Stop messaging me", "Unsubscribe", "Don't contact me again", "Remove my number"
9. "unclear" — Reply is ambiguous, single emoji, too brief, or completely unrelated.
   Examples: "Ok", "👍", "Hmm", "K", "Who are you?"

### CRITICAL CLASSIFICATION RULES
1. Multi-language: The reply may be in English, Hindi, or Hinglish (e.g. "Call karo" -> "meeting_request", "Charges kya hai?" -> "pricing_request").
2. "Ok" alone or a single thumbs up/emoji is ambiguous and MUST be classified as "unclear" with confidence below 0.7.
3. If they ask to talk or call, choose "meeting_request" even if casual ("call me").
4. "opt_out" is reserved for explicit demands to stop or unsubscribe.
5. Provide a confidence score between 0.0 and 1.0. Set confidence strictly below 0.7 for ambiguous, vague, or sarcastic replies.

### OUTPUT SPECIFICATION
You MUST respond with a single valid JSON object with NO surrounding markdown or backticks.
Conform strictly to this JSON schema:
{{
  "classification": "<one of the 9 categories above>",
  "confidence": 0.95,
  "reasoning": "Brief explanation of why this category was selected.",
  "suggested_action": "Recommended next step for the sales rep."
}}"""

    return prompt

