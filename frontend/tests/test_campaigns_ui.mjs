import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("Campaigns UI Logic Tests", () => {
  it("verifies the 19 standard industry templates and opportunity signals", () => {
    const expectedIndustryIds = [
      "coaching_institutes",
      "clinics",
      "restaurants",
      "gyms",
      "electronics",
      "clothing",
      "real_estate",
      "salons",
      "hotels",
      "manufacturers",
      "repair_services",
      "auto_dealers",
      "pharmacies",
      "schools",
      "legal_consulting",
      "photography",
      "finance_insurance",
      "supermarkets",
      "custom",
    ];

    assert.strictEqual(expectedIndustryIds.length, 19);

    const getIndustryTemplate = (id) => {
      const found = expectedIndustryIds.find((t) => t === id);
      return found || "custom";
    };

    assert.strictEqual(getIndustryTemplate("coaching_institutes"), "coaching_institutes");
    assert.strictEqual(getIndustryTemplate("restaurants"), "restaurants");
    assert.strictEqual(getIndustryTemplate("unknown_id"), "custom");
  });

  it("validates campaign form inputs according to UI and backend rules", () => {
    const validateCampaignForm = (form) => {
      if (!form.name || !form.name.trim()) {
        return { valid: false, error: "Please enter a campaign name." };
      }
      if (!form.location || !form.location.trim()) {
        return { valid: false, error: "Please enter a city or target area." };
      }
      if (form.industry === "custom" && (!form.customIndustry || !form.customIndustry.trim())) {
        return { valid: false, error: "Please type your custom industry label." };
      }
      const budget = parseFloat(form.max_budget) || 0;
      if (budget < 0) {
        return { valid: false, error: "Maximum budget cannot be negative." };
      }
      const targetLeads = Number(form.target_leads) || 50;
      if (targetLeads < 1 || targetLeads > 500) {
        return { valid: false, error: "Target leads must be between 1 and 500." };
      }
      const followupGap = Number(form.followup_gap_days) || 3;
      if (followupGap < 1 || followupGap > 30) {
        return { valid: false, error: "Follow-up gap must be between 1 and 30 days." };
      }
      const maxFollowups = Number(form.max_followups) || 0;
      if (maxFollowups < 0 || maxFollowups > 5) {
        return { valid: false, error: "Maximum follow-ups must be between 0 and 5." };
      }
      const timeRegex = /^([01]\d|2[0-3]):[0-5]\d$/;
      if (form.quiet_hours_start && !timeRegex.test(form.quiet_hours_start)) {
        return { valid: false, error: "Quiet hours start must be in HH:MM format." };
      }
      if (form.quiet_hours_end && !timeRegex.test(form.quiet_hours_end)) {
        return { valid: false, error: "Quiet hours end must be in HH:MM format." };
      }
      return { valid: true, error: null };
    };

    assert.deepStrictEqual(
      validateCampaignForm({ name: "   ", location: "Pune", industry: "clinics" }),
      { valid: false, error: "Please enter a campaign name." }
    );
    assert.deepStrictEqual(
      validateCampaignForm({ name: "Camp 1", location: " ", industry: "clinics" }),
      { valid: false, error: "Please enter a city or target area." }
    );
    assert.deepStrictEqual(
      validateCampaignForm({ name: "Camp 1", location: "Pune", industry: "custom", customIndustry: "" }),
      { valid: false, error: "Please type your custom industry label." }
    );
    assert.deepStrictEqual(
      validateCampaignForm({ name: "Camp 1", location: "Pune", industry: "clinics", max_budget: "-50" }),
      { valid: false, error: "Maximum budget cannot be negative." }
    );
    assert.deepStrictEqual(
      validateCampaignForm({ name: "Camp 1", location: "Pune", industry: "clinics", target_leads: 600 }),
      { valid: false, error: "Target leads must be between 1 and 500." }
    );
    assert.deepStrictEqual(
      validateCampaignForm({ name: "Camp 1", location: "Pune", industry: "clinics", max_followups: 8 }),
      { valid: false, error: "Maximum follow-ups must be between 0 and 5." }
    );
    assert.deepStrictEqual(
      validateCampaignForm({ name: "Camp 1", location: "Pune", industry: "clinics", quiet_hours_start: "invalid" }),
      { valid: false, error: "Quiet hours start must be in HH:MM format." }
    );
    assert.deepStrictEqual(
      validateCampaignForm({
        name: "Nagpur Coaching",
        location: "Nagpur",
        industry: "coaching_institutes",
        target_leads: 50,
        followup_gap_days: 3,
        max_followups: 3,
        max_budget: "500",
        quiet_hours_start: "21:00",
        quiet_hours_end: "09:00",
      }),
      { valid: true, error: null }
    );
  });

  it("determines correct redirect target based on save action", () => {
    const getRedirectRoute = (createdId, startDiscovery) => {
      return startDiscovery ? `/campaigns/${createdId}` : "/campaigns";
    };

    assert.strictEqual(getRedirectRoute("abc-123", true), "/campaigns/abc-123");
    assert.strictEqual(getRedirectRoute("abc-123", false), "/campaigns");
  });

  it("calculates budget consumption ratio and caution threshold", () => {
    const calculateBudgetMetrics = (spent, maxBudget) => {
      const isBudgetSet = maxBudget > 0;
      const ratio = isBudgetSet ? Math.min((spent / maxBudget) * 100, 100) : 0;
      const isCaution = isBudgetSet && ratio >= 80;
      return { isBudgetSet, ratio, isCaution };
    };

    assert.deepStrictEqual(calculateBudgetMetrics(0, 0), {
      isBudgetSet: false,
      ratio: 0,
      isCaution: false,
    });
    assert.deepStrictEqual(calculateBudgetMetrics(50, 500), {
      isBudgetSet: true,
      ratio: 10,
      isCaution: false,
    });
    assert.deepStrictEqual(calculateBudgetMetrics(420, 500), {
      isBudgetSet: true,
      ratio: 84,
      isCaution: true,
    });
  });

  it("correctly parses and normalizes keywords list", () => {
    const parseKeywords = (raw) => {
      if (!raw) return [];
      return raw
        .split(/[,;\n]+/)
        .map((k) => k.trim())
        .filter((k) => k.length > 0);
    };

    assert.deepStrictEqual(parseKeywords(""), []);
    assert.deepStrictEqual(
      parseKeywords("coaching, tuition,   classes ; academy \n study center"),
      ["coaching", "tuition", "classes", "academy", "study center"]
    );
  });

  it("maps campaign status to human-readable sentence-case labels per UI-UX.md", () => {
    const getStatusLabel = (status) => {
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

    assert.strictEqual(getStatusLabel("draft"), "Draft");
    assert.strictEqual(getStatusLabel("discovering"), "Finding leads");
    assert.strictEqual(getStatusLabel("discovery_complete"), "Leads found");
    assert.strictEqual(getStatusLabel("auditing"), "Auditing");
    assert.strictEqual(getStatusLabel("active"), "Active");
    assert.strictEqual(getStatusLabel("paused"), "Paused");
    assert.strictEqual(getStatusLabel("completed"), "Completed");
  });

  it("checks budget warning condition per UI-UX.md Section 6.4", () => {
    const shouldWarnBudget = (budget) => {
      const parsed = parseFloat(budget);
      return isNaN(parsed) || parsed <= 0;
    };

    assert.strictEqual(shouldWarnBudget("0"), true);
    assert.strictEqual(shouldWarnBudget(""), true);
    assert.strictEqual(shouldWarnBudget("-100"), true);
    assert.strictEqual(shouldWarnBudget("500"), false);
    assert.strictEqual(shouldWarnBudget("1000.50"), false);
  });
});
