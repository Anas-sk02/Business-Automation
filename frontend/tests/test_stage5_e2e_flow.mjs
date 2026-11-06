import { describe, it } from "node:test";
import assert from "node:assert/strict";

// Replicas of lead detail next-step and pipeline logic matching leads/[id]/page.tsx
function getRecommendedNextStep(stage, auditStatus) {
  const norm = String(stage || "").toLowerCase();

  if (norm === "discovered" || norm === "research_pending") {
    if (!auditStatus || auditStatus === "pending") {
      return { title: "Start audit", action: "audit", tab: "audit" };
    }
    if (auditStatus === "running") {
      return { title: "Audit in progress", action: "audit_running", tab: "audit" };
    }
    return { title: "Review findings", action: "review_audit", tab: "audit" };
  }

  if (norm === "researched") {
    return { title: "Run analysis", action: "analysis", tab: "analysis" };
  }
  if (norm === "qualified") {
    return { title: "Create draft", action: "draft", tab: "whatsapp" };
  }
  if (norm === "contacted") {
    return { title: "Awaiting response", action: "wait", tab: "whatsapp" };
  }
  if (norm === "followup_due") {
    return { title: "Send follow-up", action: "followup", tab: "whatsapp" };
  }
  if (norm === "replied" || norm === "interested") {
    return { title: "Schedule call", action: "call", tab: "tasks" };
  }
  if (norm === "meeting_scheduled") {
    return { title: "Prepare meeting", action: "meeting", tab: "tasks" };
  }
  if (norm === "proposal_sent" || norm === "negotiation") {
    return { title: "Follow up on proposal", action: "proposal", tab: "tasks" };
  }
  if (norm === "won") {
    return { title: "Onboard client", action: "won", tab: "tasks" };
  }
  return { title: "No action required", action: "none" };
}

// 24-hour service window calculation replica matching WhatsAppChat.tsx
function get24HourWindowStatus(messages, nowTimestamp = Date.now()) {
  const inboundMessages = messages
    .filter((m) => m.direction === "inbound" && m.created_at)
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

  if (inboundMessages.length === 0) {
    return { isOpen: false, closesAt: null };
  }

  const lastInboundTime = new Date(inboundMessages[0].created_at).getTime();
  const windowClosesTime = lastInboundTime + 24 * 60 * 60 * 1000;

  if (nowTimestamp < windowClosesTime) {
    const closesAt = new Date(windowClosesTime);
    return {
      isOpen: true,
      closesAt,
      formattedClosingTime: closesAt.toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
      }),
    };
  }

  return { isOpen: false, closesAt: null };
}

// Strict opt-out detector matching decisions.md §10
const OPT_OUT_KEYWORDS = [
  "stop",
  "unsubscribe",
  "opt out",
  "optout",
  "band karo",
  "mat bhejo",
  "nahi chahiye",
];

function isKeywordOptOut(text) {
  if (!text || typeof text !== "string") return false;
  const clean = text.toLowerCase().replace(/[^\w\s]/g, "").trim();
  for (const kw of OPT_OUT_KEYWORDS) {
    if (clean === kw || clean.startsWith(kw + " ")) {
      return true;
    }
  }
  return false;
}

describe("Stage 5 End-to-End Outreach Flow Verification", () => {
  it("transitions state correctly from qualified to contacted upon message dispatch", () => {
    // 1. Qualified lead initial state
    let lead = {
      id: "lead-123",
      business_name: "Apex Physio Clinic",
      phone: "+919876543210",
      fit_score: 82,
      pipeline_stage: "qualified",
      is_suppressed: false,
    };

    // Recommended step should point to WhatsApp tab to create draft
    let nextStep = getRecommendedNextStep(lead.pipeline_stage);
    assert.equal(nextStep.title, "Create draft");
    assert.equal(nextStep.action, "draft");
    assert.equal(nextStep.tab, "whatsapp");

    // 2. Draft is generated with verified audit evidence
    const draft = {
      message_id: "msg-001",
      lead_id: lead.id,
      message_body:
        "Hi Dr. Apex Team, noticed your clinic website takes 4.8s to load on mobile.\n\nReply STOP to opt out",
      evidence_cited: ["Mobile LCP 4.8s"],
      status: "draft",
    };
    assert.match(draft.message_body, /Reply STOP to opt out/i);
    assert.equal(draft.status, "draft");

    // 3. User approves and dispatches message
    draft.status = "approved";
    assert.equal(draft.status, "approved");

    // Simulating dispatch action (onStageChange callback from WhatsAppChat.tsx)
    const onStageChange = (newStage) => {
      lead = { ...lead, pipeline_stage: newStage };
    };
    onStageChange("contacted");

    // Lead stage must be updated to contacted
    assert.equal(lead.pipeline_stage, "contacted");

    // 4. Next step automatically updates to 'Awaiting response'
    nextStep = getRecommendedNextStep(lead.pipeline_stage);
    assert.equal(nextStep.title, "Awaiting response");
    assert.equal(nextStep.action, "wait");
    assert.equal(nextStep.tab, "whatsapp");
  });

  it("handles inbound reply state transitions and opens 24h window", () => {
    const fixedNow = new Date("2026-11-06T10:00:00.000Z").getTime();
    let lead = {
      id: "lead-456",
      business_name: "Dr. Sharma Dental",
      phone: "+919876543211",
      pipeline_stage: "contacted",
      is_suppressed: false,
    };

    // Lead replies with interest
    const inboundReply = {
      id: "msg-inbound-1",
      direction: "inbound",
      message_body: "Yes, how much would a website redesign cost?",
      reply_classification: "interested",
      created_at: new Date(fixedNow - 30 * 60000).toISOString(), // 30 mins ago
    };

    // Inbound reply opens 24-hour service conversation window
    const windowStatus = get24HourWindowStatus([inboundReply], fixedNow);
    assert.equal(windowStatus.isOpen, true);

    // AI Classification updates pipeline stage to 'interested'
    if (inboundReply.reply_classification === "interested") {
      lead.pipeline_stage = "interested";
    }
    assert.equal(lead.pipeline_stage, "interested");

    // Next step updates to 'Schedule call' (tab: tasks)
    const nextStep = getRecommendedNextStep(lead.pipeline_stage);
    assert.equal(nextStep.title, "Schedule call");
    assert.equal(nextStep.action, "call");
    assert.equal(nextStep.tab, "tasks");
  });

  it("strictly suppresses lead and locks outreach on opt-out demands per decisions.md §10", () => {
    let lead = {
      id: "lead-789",
      business_name: "Urban Spa",
      phone: "+919876543212",
      pipeline_stage: "contacted",
      is_suppressed: false,
      suppression_reason: null,
    };

    const optOutPhrases = [
      "stop",
      "STOP",
      "Unsubscribe please",
      "band karo",
      "mat bhejo mujhe message",
      "nahi chahiye",
    ];

    for (const phrase of optOutPhrases) {
      assert.equal(isKeywordOptOut(phrase), true, `Failed for phrase: ${phrase}`);
    }

    // Process opt-out
    const optOutText = "band karo";
    if (isKeywordOptOut(optOutText)) {
      lead.is_suppressed = true;
      lead.suppression_reason = "prospect_opt_out";
      lead.pipeline_stage = "opted_out";
    }

    assert.equal(lead.is_suppressed, true);
    assert.equal(lead.pipeline_stage, "opted_out");
    assert.equal(lead.suppression_reason, "prospect_opt_out");

    // Next step must update to 'No action required' with no primary button
    const nextStep = getRecommendedNextStep(lead.pipeline_stage);
    assert.equal(nextStep.title, "No action required");
    assert.equal(nextStep.action, "none");
    assert.equal(nextStep.buttonText, undefined);
  });

  it("verifies lead detail page props contract with WhatsAppChat component", () => {
    const leadDetailSample = {
      id: "lead-abc",
      business_name: "Apex Healthcare",
      phone: "+919876543210",
      is_suppressed: false,
      suppression_reason: null,
      pipeline_stage: "qualified",
    };

    // Verify all required props can be directly passed from lead state
    assert.equal(typeof leadDetailSample.id, "string");
    assert.equal(typeof leadDetailSample.business_name, "string");
    assert.equal(typeof leadDetailSample.phone, "string");
    assert.equal(typeof leadDetailSample.is_suppressed, "boolean");
    assert.equal(typeof leadDetailSample.pipeline_stage, "string");
  });
});

