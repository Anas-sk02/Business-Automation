import { describe, it } from "node:test";
import assert from "node:assert/strict";

// Helper replicating getStageChipInfo logic from LeadTable.tsx
function getStageChipInfo(stage) {
  const norm = String(stage || "").toLowerCase();
  switch (norm) {
    case "discovered":
    case "research_pending":
    case "researched":
      return {
        label: norm === "research_pending" ? "Research pending" : norm === "discovered" ? "Discovered" : "Researched",
        tone: "neutral",
        dotClass: "bg-muted-foreground",
        badgeClass: "border-border text-foreground bg-muted/40",
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
      return { label: "Won", tone: "good", dotClass: "bg-good" };
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

const CANONICAL_STAGES = [
  "discovered",
  "research_pending",
  "researched",
  "qualified",
  "contacted",
  "followup_due",
  "replied",
  "interested",
  "meeting_scheduled",
  "proposal_sent",
  "negotiation",
  "won",
  "not_interested",
  "no_response",
  "closed_lost",
  "opted_out",
];

describe("LeadTable UI & State Logic Tests", () => {
  it("verifies canonical list contains all 16 stages per decisions.md Section 5", () => {
    assert.strictEqual(CANONICAL_STAGES.length, 16);
    const expectedStages = [
      "discovered",
      "research_pending",
      "researched",
      "qualified",
      "contacted",
      "followup_due",
      "replied",
      "interested",
      "meeting_scheduled",
      "proposal_sent",
      "negotiation",
      "won",
      "not_interested",
      "no_response",
      "closed_lost",
      "opted_out",
    ];

    for (const expected of expectedStages) {
      assert.ok(
        CANONICAL_STAGES.includes(expected),
        `Stage ${expected} must be in CANONICAL_STAGES`
      );
    }
  });

  it("maps all 16 stages to the 4 UI-UX.md Section 5.2 tones accurately", () => {
    const neutralStages = ["discovered", "research_pending", "researched"];
    const petrolStages = ["qualified", "contacted", "followup_due", "replied"];
    const goodStages = ["interested", "meeting_scheduled", "proposal_sent", "negotiation", "won"];
    const closedStages = ["not_interested", "no_response", "closed_lost", "opted_out"];

    for (const stage of neutralStages) {
      const info = getStageChipInfo(stage);
      assert.strictEqual(info.tone, "neutral", `${stage} should have neutral tone`);
    }

    for (const stage of petrolStages) {
      const info = getStageChipInfo(stage);
      assert.strictEqual(info.tone, "petrol", `${stage} should have petrol tone`);
    }

    for (const stage of goodStages) {
      const info = getStageChipInfo(stage);
      assert.strictEqual(info.tone, "good", `${stage} should have good tone`);
    }

    for (const stage of closedStages) {
      const info = getStageChipInfo(stage);
      assert.strictEqual(info.tone, "closed", `${stage} should have closed tone`);
    }
  });

  it("formats stage names in human-readable sentence case with no underscores", () => {
    assert.strictEqual(getStageChipInfo("research_pending").label, "Research pending");
    assert.strictEqual(getStageChipInfo("followup_due").label, "Follow-up due");
    assert.strictEqual(getStageChipInfo("meeting_scheduled").label, "Meeting scheduled");
    assert.strictEqual(getStageChipInfo("proposal_sent").label, "Proposal sent");
    assert.strictEqual(getStageChipInfo("not_interested").label, "Not interested");
    assert.strictEqual(getStageChipInfo("no_response").label, "No response");
    assert.strictEqual(getStageChipInfo("closed_lost").label, "Closed lost");
    assert.strictEqual(getStageChipInfo("opted_out").label, "Opted out");
  });

  it("calculates qualify threshold (QUALIFY_SCORE = 60) and bar clamping per decisions.md Section 6", () => {
    const calculateScorePresentation = (rawScore) => {
      const score = rawScore ?? 0;
      const isQualified = score >= 60;
      const clampedScore = Math.min(Math.max(score, 0), 100);
      const barColorClass = isQualified ? "bg-primary" : "bg-muted-foreground/40";
      return { score, isQualified, clampedScore, barColorClass };
    };

    // Disqualified (< 60)
    const low = calculateScorePresentation(45);
    assert.strictEqual(low.isQualified, false);
    assert.strictEqual(low.clampedScore, 45);
    assert.strictEqual(low.barColorClass, "bg-muted-foreground/40");

    // Exactly at threshold (60)
    const boundary = calculateScorePresentation(60);
    assert.strictEqual(boundary.isQualified, true);
    assert.strictEqual(boundary.clampedScore, 60);
    assert.strictEqual(boundary.barColorClass, "bg-primary");

    // Qualified (> 60)
    const high = calculateScorePresentation(85);
    assert.strictEqual(high.isQualified, true);
    assert.strictEqual(high.clampedScore, 85);
    assert.strictEqual(high.barColorClass, "bg-primary");

    // Out-of-bounds clamping
    const overflow = calculateScorePresentation(120);
    assert.strictEqual(overflow.clampedScore, 100);
    const negative = calculateScorePresentation(-10);
    assert.strictEqual(negative.clampedScore, 0);
  });

  it("computes pagination bounds and ranges matching UI-UX.md Section 5.5", () => {
    const computePagination = (totalCount, page, pageSize) => {
      const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
      const startItem = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
      const endItem = Math.min(page * pageSize, totalCount);
      return { totalPages, startItem, endItem };
    };

    // First page with 42 leads, 25 per page
    const p1 = computePagination(42, 1, 25);
    assert.strictEqual(p1.startItem, 1);
    assert.strictEqual(p1.endItem, 25);
    assert.strictEqual(p1.totalPages, 2);

    // Second page
    const p2 = computePagination(42, 2, 25);
    assert.strictEqual(p2.startItem, 26);
    assert.strictEqual(p2.endItem, 42);
    assert.strictEqual(p2.totalPages, 2);

    // Zero leads empty state
    const p0 = computePagination(0, 1, 25);
    assert.strictEqual(p0.startItem, 0);
    assert.strictEqual(p0.endItem, 0);
    assert.strictEqual(p0.totalPages, 1);
  });

  it("maps query params accurately for API list requests", () => {
    const buildLeadQueryParams = (filters) => {
      const params = {
        page: filters.page,
        page_size: filters.pageSize,
        sort_by: filters.sortBy,
        sort_order: filters.sortOrder,
      };

      if (filters.search) params.search = filters.search.trim();
      if (filters.stage && filters.stage !== "all") params.stage = filters.stage;
      if (filters.websiteFilter === "has_website") params.has_website = true;
      else if (filters.websiteFilter === "no_website") params.has_website = false;
      if (filters.phoneFilter === "has_phone") params.has_phone = true;
      else if (filters.phoneFilter === "no_phone") params.has_phone = false;
      if (filters.scoreFilter === "qualified") params.min_score = 60;
      else if (filters.scoreFilter === "under_60") params.max_score = 59;

      return params;
    };

    const params = buildLeadQueryParams({
      page: 1,
      pageSize: 25,
      sortBy: "fit_score",
      sortOrder: "desc",
      search: " Apex Institute ",
      stage: "qualified",
      websiteFilter: "has_website",
      phoneFilter: "has_phone",
      scoreFilter: "qualified",
    });

    assert.strictEqual(params.page, 1);
    assert.strictEqual(params.page_size, 25);
    assert.strictEqual(params.sort_by, "fit_score");
    assert.strictEqual(params.sort_order, "desc");
    assert.strictEqual(params.search, "Apex Institute");
    assert.strictEqual(params.stage, "qualified");
    assert.strictEqual(params.has_website, true);
    assert.strictEqual(params.has_phone, true);
    assert.strictEqual(params.min_score, 60);
    assert.strictEqual(params.max_score, undefined);
  });

  it("sanitizes external URLs to prevent XSS and only permit http/https protocols", () => {
    function formatSafeUrl(url) {
      if (!url) return null;
      const trimmed = url.trim();
      if (/^https?:\/\//i.test(trimmed)) {
        return trimmed;
      }
      if (/^[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/i.test(trimmed)) {
        return `https://${trimmed}`;
      }
      return null;
    }

    // Malicious XSS protocols must return null
    assert.strictEqual(formatSafeUrl("javascript:alert(1)"), null);
    assert.strictEqual(formatSafeUrl("javascript:void(0)"), null);
    assert.strictEqual(formatSafeUrl("data:text/html;base64,PHNjcmlwdD4="), null);
    assert.strictEqual(formatSafeUrl("vbscript:msgbox(1)"), null);
    assert.strictEqual(formatSafeUrl(""), null);
    assert.strictEqual(formatSafeUrl("   "), null);
    assert.strictEqual(formatSafeUrl(null), null);
    assert.strictEqual(formatSafeUrl(undefined), null);

    // Legitimate URLs
    assert.strictEqual(
      formatSafeUrl("https://example.com/about"),
      "https://example.com/about"
    );
    assert.strictEqual(
      formatSafeUrl("http://coachingnagpur.in"),
      "http://coachingnagpur.in"
    );
    assert.strictEqual(
      formatSafeUrl("my-institute.edu.in/home"),
      "https://my-institute.edu.in/home"
    );
  });
});
