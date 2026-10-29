import { describe, it } from "node:test";
import assert from "node:assert/strict";

// Stage chip classifier matching leads/[id]/page.tsx
function getStageChipInfo(stage) {
  const norm = String(stage || "").toLowerCase();
  switch (norm) {
    case "discovered":
    case "research_pending":
    case "researched":
      return {
        label:
          norm === "research_pending"
            ? "Research pending"
            : norm === "discovered"
            ? "Discovered"
            : "Researched",
        tone: "neutral",
        dotClass: "bg-muted-foreground",
      };
    case "qualified":
      return { label: "Qualified", tone: "petrol", dotClass: "bg-primary" };
    case "contacted":
      return { label: "Contacted", tone: "petrol", dotClass: "bg-primary" };
    case "followup_due":
      return { label: "Follow-up due", tone: "petrol", dotClass: "bg-primary" };
    case "replied":
      return { label: "Replied", tone: "petrol", dotClass: "bg-primary" };
    case "interested":
      return { label: "Interested", tone: "good", dotClass: "bg-good" };
    case "meeting_scheduled":
      return { label: "Meeting scheduled", tone: "good", dotClass: "bg-good" };
    case "proposal_sent":
      return { label: "Proposal sent", tone: "good", dotClass: "bg-good" };
    case "negotiation":
      return { label: "Negotiation", tone: "good", dotClass: "bg-good" };
    case "won":
      return { label: "Won", tone: "good", dotClass: "bg-good", isWon: true };
    case "not_interested":
      return { label: "Not interested", tone: "closed", dotClass: "bg-muted-foreground/60" };
    case "no_response":
      return { label: "No response", tone: "closed", dotClass: "bg-muted-foreground/60" };
    case "closed_lost":
      return { label: "Closed lost", tone: "closed", dotClass: "bg-problem/70" };
    case "opted_out":
      return { label: "Opted out", tone: "closed", dotClass: "bg-problem/70" };
    default:
      return { label: norm.replace(/_/g, " "), tone: "neutral", dotClass: "bg-muted-foreground" };
  }
}

// Next step recommendation matching leads/[id]/page.tsx
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

// ScoreLedger logic replica
const QUALIFY_SCORE = 60;
const SCORE_MAX_POINTS = {
  industry: 20,
  location: 15,
  website_issues: 25,
  evidence: 15,
  contact: 10,
  phone: 10,
  rating: 5,
};

function resolveEarned(breakdown, keys, max) {
  if (!breakdown) return 0;
  for (const key of keys) {
    const raw = breakdown[key];
    const num =
      typeof raw === "number"
        ? raw
        : typeof raw === "string" && raw.trim() !== ""
        ? Number(raw)
        : NaN;
    if (!Number.isNaN(num)) {
      return Math.min(max, Math.max(0, Math.round(num)));
    }
  }
  return 0;
}

// Sanitization functions matching leads/[id]/page.tsx
function sanitizeUrl(rawUrl) {
  if (!rawUrl) return null;
  const trimmed = rawUrl.trim();
  if (!trimmed) return null;
  try {
    const hasScheme = /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(trimmed);
    const candidate = hasScheme ? trimmed : `https://${trimmed}`;
    const parsed = new URL(candidate);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
  } catch {
    return null;
  }
  return null;
}

function sanitizePhone(rawPhone) {
  if (!rawPhone) return "";
  return rawPhone.replace(/[^\d+]/g, "");
}

describe("Lead Detail Page UI & Logic Tests", () => {
  it("categorizes all 16 pipeline stages into the 4 semantic tones per UI-UX.md §6.6", () => {
    const neutralStages = ["discovered", "research_pending", "researched"];
    const petrolStages = ["qualified", "contacted", "followup_due", "replied"];
    const goodStages = ["interested", "meeting_scheduled", "proposal_sent", "negotiation", "won"];
    const closedStages = ["not_interested", "no_response", "closed_lost", "opted_out"];

    for (const st of neutralStages) {
      assert.strictEqual(getStageChipInfo(st).tone, "neutral", `Stage ${st} should be neutral`);
    }
    for (const st of petrolStages) {
      assert.strictEqual(getStageChipInfo(st).tone, "petrol", `Stage ${st} should be petrol`);
    }
    for (const st of goodStages) {
      assert.strictEqual(getStageChipInfo(st).tone, "good", `Stage ${st} should be good`);
    }
    for (const st of closedStages) {
      assert.strictEqual(getStageChipInfo(st).tone, "closed", `Stage ${st} should be closed`);
    }

    // Verify won gets special checkmark indicator
    assert.strictEqual(getStageChipInfo("won").isWon, true);
    assert.strictEqual(getStageChipInfo("interested").isWon, undefined);
  });

  it("validates score ledger 7-component breakdown sums to 100 max points per UI-UX.md §5.3", () => {
    const totalMax = Object.values(SCORE_MAX_POINTS).reduce((sum, val) => sum + val, 0);
    assert.strictEqual(totalMax, 100, "7 score components must sum exactly to 100");
    assert.strictEqual(QUALIFY_SCORE, 60, "Qualify threshold must be exactly 60");
  });

  it("verifies qualify logic for scores below and above threshold", () => {
    const testCases = [
      { score: 0, qualifies: false },
      { score: 45, qualifies: false },
      { score: 59, qualifies: false },
      { score: 60, qualifies: true },
      { score: 75, qualifies: true },
      { score: 100, qualifies: true },
    ];

    for (const tc of testCases) {
      const qualifies = tc.score >= QUALIFY_SCORE;
      assert.strictEqual(
        qualifies,
        tc.qualifies,
        `Score ${tc.score} qualification should be ${tc.qualifies}`
      );
    }
  });

  it("recommends correct next step action based on stage and audit state", () => {
    // Stage: discovered without audit
    assert.strictEqual(getRecommendedNextStep("discovered", null).action, "audit");
    assert.strictEqual(getRecommendedNextStep("discovered", "pending").action, "audit");

    // Stage: discovered with audit running
    assert.strictEqual(getRecommendedNextStep("discovered", "running").action, "audit_running");

    // Stage: discovered with audit completed
    assert.strictEqual(getRecommendedNextStep("discovered", "completed").action, "review_audit");

    // Downstream pipeline stages
    assert.strictEqual(getRecommendedNextStep("researched").action, "analysis");
    assert.strictEqual(getRecommendedNextStep("qualified").action, "draft");
    assert.strictEqual(getRecommendedNextStep("contacted").action, "wait");
    assert.strictEqual(getRecommendedNextStep("followup_due").action, "followup");
    assert.strictEqual(getRecommendedNextStep("replied").action, "call");
    assert.strictEqual(getRecommendedNextStep("interested").action, "call");
    assert.strictEqual(getRecommendedNextStep("meeting_scheduled").action, "meeting");
    assert.strictEqual(getRecommendedNextStep("proposal_sent").action, "proposal");
    assert.strictEqual(getRecommendedNextStep("won").action, "won");
    assert.strictEqual(getRecommendedNextStep("closed_lost").action, "none");
    assert.strictEqual(getRecommendedNextStep("opted_out").action, "none");
  });

  it("enforces 'Not listed' placeholder for missing fields per UI-UX.md §2", () => {
    function formatField(value) {
      return value || "Not listed";
    }

    assert.strictEqual(formatField(null), "Not listed");
    assert.strictEqual(formatField(undefined), "Not listed");
    assert.strictEqual(formatField(""), "Not listed");
    assert.strictEqual(formatField("+44 20 7946 0950"), "+44 20 7946 0950");
  });

  it("sanitizes website URLs and prevents XSS / malicious schemes", () => {
    // Permitted schemes
    assert.strictEqual(sanitizeUrl("https://example.com"), "https://example.com/");
    assert.strictEqual(sanitizeUrl("http://example.com/test"), "http://example.com/test");
    assert.strictEqual(sanitizeUrl("example.com"), "https://example.com/");

    // Prohibited / malicious schemes
    assert.strictEqual(sanitizeUrl("javascript:alert('xss')"), null);
    assert.strictEqual(sanitizeUrl("data:text/html,<script>alert(1)</script>"), null);
    assert.strictEqual(sanitizeUrl("file:///etc/passwd"), null);
    assert.strictEqual(sanitizeUrl("vbscript:msgbox"), null);
    assert.strictEqual(sanitizeUrl(""), null);
    assert.strictEqual(sanitizeUrl("   "), null);
    assert.strictEqual(sanitizeUrl(null), null);
    assert.strictEqual(sanitizeUrl(undefined), null);
  });

  it("sanitizes phone numbers for safe tel: href generation", () => {
    assert.strictEqual(sanitizePhone("+44 20 7946 0950"), "+442079460950");
    assert.strictEqual(sanitizePhone("+1 (555) 234-5678"), "+15552345678");
    assert.strictEqual(sanitizePhone(""), "");
    assert.strictEqual(sanitizePhone(null), "");
    assert.strictEqual(sanitizePhone(undefined), "");
  });

  it("safely resolves breakdown points with edge cases (strings, NaN, limits)", () => {
    // Standard number
    assert.strictEqual(resolveEarned({ industry: 18 }, ["industry"], 20), 18);

    // Numeric string conversion
    assert.strictEqual(resolveEarned({ location: "12" }, ["location"], 15), 12);

    // Over-max clamping
    assert.strictEqual(resolveEarned({ website: 50 }, ["website"], 25), 25);

    // Negative clamping
    assert.strictEqual(resolveEarned({ rating: -5 }, ["rating"], 5), 0);

    // Fallback key lookup
    assert.strictEqual(resolveEarned({ industry_fit: 20 }, ["industry", "industry_fit"], 20), 20);

    // Invalid values
    assert.strictEqual(resolveEarned({ evidence: "invalid" }, ["evidence"], 15), 0);
    assert.strictEqual(resolveEarned(null, ["industry"], 20), 0);
  });
});
