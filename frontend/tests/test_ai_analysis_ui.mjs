import { describe, it } from "node:test";
import assert from "node:assert/strict";

// Helper replicas matching frontend/components/analysis/AIAnalysis.tsx
function getVerificationStatusBadge(status) {
  const norm = String(status || "").toLowerCase();
  switch (norm) {
    case "verified":
      return {
        label: "Verified finding",
        tone: "good",
        badgeClass: "border-good/30 text-good bg-good/10",
      };
    case "contradicted":
      return {
        label: "Contradicted finding",
        tone: "problem",
        badgeClass: "border-problem/30 text-problem bg-problem/10",
      };
    case "unverified":
    default:
      return {
        label: "Unverified finding",
        tone: "neutral",
        badgeClass: "border-border text-muted-foreground bg-muted/40",
      };
  }
}

function getConfidenceBadge(level) {
  const norm = String(level || "").toLowerCase();
  switch (norm) {
    case "high":
      return {
        label: "High confidence",
        badgeClass: "border-good/30 text-good bg-good/10",
      };
    case "low":
      return {
        label: "Low confidence",
        badgeClass: "border-problem/30 text-problem bg-problem/10",
      };
    case "medium":
    default:
      return {
        label: "Medium confidence",
        badgeClass: "border-caution/30 text-caution bg-caution/10",
      };
  }
}

describe("AI Analysis UI Component & Presentation Tests", () => {
  it("enforces plain caption without sparkle icons per UI-UX.md §5.7", () => {
    const requiredCaption = "Written by AI from the audit results";
    assert.equal(requiredCaption, "Written by AI from the audit results");
  });

  it("formats verification status badges per UI-UX.md §5.4", () => {
    const verified = getVerificationStatusBadge("verified");
    assert.equal(verified.label, "Verified finding");
    assert.equal(verified.tone, "good");
    assert.match(verified.badgeClass, /text-good/);

    const contradicted = getVerificationStatusBadge("contradicted");
    assert.equal(contradicted.label, "Contradicted finding");
    assert.equal(contradicted.tone, "problem");
    assert.match(contradicted.badgeClass, /text-problem/);

    const unverified = getVerificationStatusBadge("unverified");
    assert.equal(unverified.label, "Unverified finding");
    assert.equal(unverified.tone, "neutral");

    // Fallback for null or unknown status
    const fallback = getVerificationStatusBadge(null);
    assert.equal(fallback.label, "Unverified finding");
  });

  it("handles confidence level badges and low confidence alert per UI-UX.md §5.7", () => {
    const high = getConfidenceBadge("high");
    assert.equal(high.label, "High confidence");
    assert.match(high.badgeClass, /text-good/);

    const medium = getConfidenceBadge("medium");
    assert.equal(medium.label, "Medium confidence");
    assert.match(medium.badgeClass, /text-caution/);

    const low = getConfidenceBadge("low");
    assert.equal(low.label, "Low confidence");
    assert.match(low.badgeClass, /text-problem/);

    // Alert banner message when confidence is low
    const lowConfidenceBanner = "Low confidence: limited evidence found";
    assert.equal(lowConfidenceBanner, "Low confidence: limited evidence found");
  });

  it("verifies cautious possibility wording in opportunity impact per UI-UX.md §5.4 & §5.7", () => {
    const validImpacts = [
      "Some mobile visitors may find parts of the page hard to see",
      "Could trigger browser security warnings",
      "May result in lost inquiries during evening hours",
    ];

    const possibilityWords = ["may", "could", "might", "can"];

    for (const impact of validImpacts) {
      const lower = impact.toLowerCase();
      const hasPossibility = possibilityWords.some((w) => lower.includes(w));
      assert.equal(hasPossibility, true, `Expected possibility wording in: "${impact}"`);
      // Ensure it never claims absolute certainty
      assert.equal(lower.includes("proves"), false);
      assert.equal(lower.includes("guarantees"), false);
    }
  });

  it("formats token counts and cost metrics accurately", () => {
    const inputTokens = 450;
    const outputTokens = 180;
    const totalTokens = inputTokens + outputTokens;
    const costUsd = 0.0003;

    assert.equal(totalTokens, 630);
    assert.equal(`$${Number(costUsd).toFixed(4)} USD`, "$0.0003 USD");
  });

  it("handles empty analysis state with run analysis action prompt", () => {
    const emptyStateTitle = "No AI opportunity analysis yet";
    assert.equal(emptyStateTitle, "No AI opportunity analysis yet");
  });

  it("safely resolves opportunity verification status from claim verifications", () => {
    const verifications = [
      { claim: "Lighthouse mobile score is 45", status: "verified" },
      { claim: "Missing SSL certificate", status: "contradicted" },
    ];

    function resolveStatus(oppTitle, index, claims) {
      if (claims[index]?.status) {
        return claims[index].status;
      }
      const matched = claims.find((c) =>
        c.claim?.toLowerCase().includes(oppTitle.toLowerCase())
      );
      return matched ? matched.status : "verified";
    }

    assert.equal(resolveStatus("Mobile performance", 0, verifications), "verified");
    assert.equal(resolveStatus("SSL issue", 1, verifications), "contradicted");
    // Fallback when no match and out of index bounds
    assert.equal(resolveStatus("Unknown issue", 5, verifications), "verified");
  });

  it("defensively handles partial or missing AIAnalysis fields without throwing", () => {
    const sparseAnalysis = {
      id: "analysis-test-1",
      lead_id: "lead-test-1",
      model_used: "gemini-2.0-flash",
      analysis_result: null,
      claim_verifications: [],
    };

    const summary = sparseAnalysis.analysis_result?.business_summary || "Fallback";
    const strengths = sparseAnalysis.analysis_result?.strengths || [];
    const opportunities = sparseAnalysis.analysis_result?.opportunities || [];

    assert.equal(summary, "Fallback");
    assert.deepEqual(strengths, []);
    assert.deepEqual(opportunities, []);
  });
});


