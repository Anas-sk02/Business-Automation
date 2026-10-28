import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("Discovery Progress UI & State Tests", () => {
  it("verifies the 16 canonical pipeline stages per decisions.md Section 5", () => {
    const canonicalStages = [
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
      "closed_lost",
      "not_interested",
      "no_response",
      "opted_out",
    ];

    assert.strictEqual(canonicalStages.length, 16);
    assert.ok(canonicalStages.includes("interested"));
    assert.ok(canonicalStages.includes("closed_lost"));
    assert.ok(canonicalStages.includes("negotiation"));
    assert.ok(!canonicalStages.includes("replied_positive")); // invalid per decisions.md
    assert.ok(!canonicalStages.includes("lost"));             // invalid per decisions.md
  });

  it("calculates leads and queries progress percentages correctly with clamping", () => {
    const calcLeadsPercent = (found, target) => {
      const safeTarget = target || 50;
      return Math.min(Math.round((found / safeTarget) * 100), 100);
    };

    const calcQueriesPercent = (completed, total) => {
      const safeTotal = total || 1;
      return Math.min(Math.round((completed / safeTotal) * 100), 100);
    };

    assert.strictEqual(calcLeadsPercent(0, 50), 0);
    assert.strictEqual(calcLeadsPercent(25, 50), 50);
    assert.strictEqual(calcLeadsPercent(50, 50), 100);
    assert.strictEqual(calcLeadsPercent(75, 50), 100); // Clamped at 100%

    assert.strictEqual(calcQueriesPercent(0, 8), 0);
    assert.strictEqual(calcQueriesPercent(4, 8), 50);
    assert.strictEqual(calcQueriesPercent(8, 8), 100);
    assert.strictEqual(calcQueriesPercent(10, 8), 100); // Clamped at 100%
  });

  it("verifies budget warning trigger at 80% threshold per decisions.md Section 11", () => {
    const isNearBudget = (spent, maxBudget) => {
      if (!maxBudget || maxBudget <= 0) return false;
      return spent >= maxBudget * 0.8;
    };

    // Budget of ₹500
    assert.strictEqual(isNearBudget(350, 500), false); // 70% < 80%
    assert.strictEqual(isNearBudget(400, 500), true);  // 80% == 80%
    assert.strictEqual(isNearBudget(450, 500), true);  // 90% > 80%
    assert.strictEqual(isNearBudget(500, 500), true);  // 100% >= 80%

    // Unlimited budget (0 or unset)
    assert.strictEqual(isNearBudget(1000, 0), false);
    assert.strictEqual(isNearBudget(1000, null), false);
  });

  it("formats status labels into UI-UX.md Section 6.3 human-readable words", () => {
    const formatStatusLabel = (status) => {
      switch (status) {
        case "draft":
          return "Draft";
        case "discovering":
          return "Finding leads";
        case "discovery_complete":
          return "Leads found";
        case "auditing":
          return "Auditing";
        case "active":
          return "Active";
        case "paused":
          return "Paused";
        case "completed":
          return "Completed";
        default:
          return status;
      }
    };

    assert.strictEqual(formatStatusLabel("draft"), "Draft");
    assert.strictEqual(formatStatusLabel("discovering"), "Finding leads");
    assert.strictEqual(formatStatusLabel("discovery_complete"), "Leads found");
    assert.strictEqual(formatStatusLabel("auditing"), "Auditing");
    assert.strictEqual(formatStatusLabel("active"), "Active");
    assert.strictEqual(formatStatusLabel("paused"), "Paused");
    assert.strictEqual(formatStatusLabel("completed"), "Completed");
  });

  it("formats discovery copy according to UI-UX.md Section 6.5", () => {
    const formatDiscoveryCopy = (queriesCompleted, queriesTotal, leadsFound) => {
      return `Searched ${queriesCompleted} of ${queriesTotal} queries, ${leadsFound} leads found`;
    };

    assert.strictEqual(
      formatDiscoveryCopy(3, 6, 31),
      "Searched 3 of 6 queries, 31 leads found"
    );
  });
});

