import { describe, it } from "node:test";
import assert from "node:assert/strict";

// Helper logic replicating frontend/components/analytics/CostBreakdown.tsx
function formatInr(amount) {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return "—";
  }
  return `₹${amount.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatUsd(amount) {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return "—";
  }
  return `$${amount.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })}`;
}

function formatServiceName(serviceKey) {
  switch (serviceKey) {
    case "google_places":
      return "Places API (Discovery)";
    case "ai_analysis":
      return "AI Website Analysis";
    case "ai_classification":
      return "AI Reply Classification";
    case "ai_message_gen":
      return "AI Message Generator";
    case "whatsapp":
      return "WhatsApp Outreach";
    case "lighthouse":
      return "Lighthouse Web Audit";
    default:
      return serviceKey
        .split("_")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
  }
}

// Logic replicating frontend/components/analytics/FunnelChart.tsx bar width with bounds clamping
function calculateFunnelBarWidth(step) {
  const safeOverallRate = Number.isFinite(step.overall_rate) ? step.overall_rate : 0;
  return step.count > 0 ? Math.min(Math.max(safeOverallRate, 3), 100) : 0;
}

// Logic replicating frontend/components/analytics/OutreachMetrics.tsx rate clamp
function clampRate(rate) {
  if (typeof rate !== "number" || !Number.isFinite(rate)) return 0;
  return Math.min(Math.max(rate, 0), 100);
}

// Logic replicating frontend/app/(dashboard)/analytics/page.tsx empty state rule
function shouldShowEmptyState(kpis) {
  return !kpis || !kpis.has_sent_messages;
}

// Logic replicating date preset calculations
function getDateRangeFromPreset(preset) {
  const now = new Date("2026-11-06T12:00:00Z");
  if (preset === "last_7_days") {
    const from = new Date(now.getTime() - 7 * 86400000);
    return { from_date: from.toISOString(), to_date: now.toISOString() };
  } else if (preset === "last_30_days") {
    const from = new Date(now.getTime() - 30 * 86400000);
    return { from_date: from.toISOString(), to_date: now.toISOString() };
  }
  return { from_date: undefined, to_date: undefined };
}

// Logic replicating service operation total calculation
function calculateTotalOperations(services) {
  if (!Array.isArray(services)) return 0;
  return services.reduce((acc, curr) => acc + (curr?.api_calls || 0), 0);
}

// Logic replicating safe endpoint path formatting
function buildAnalyticsEndpoint(selectedCampaignId, queryString) {
  if (selectedCampaignId === "all") {
    return `/api/analytics/overview${queryString}`;
  }
  const safeCampaignId = encodeURIComponent(selectedCampaignId);
  return `/api/analytics/campaign/${safeCampaignId}${queryString}`;
}

describe("Analytics UI - Currency and Name Formatting", () => {
  it("formats INR currency correctly with Indian number grouping and two decimals", () => {
    assert.strictEqual(formatInr(0), "₹0.00");
    assert.strictEqual(formatInr(150), "₹150.00");
    assert.strictEqual(formatInr(1500.5), "₹1,500.50");
    assert.strictEqual(formatInr(100000), "₹1,00,000.00");
    assert.strictEqual(formatInr(10000000), "₹1,00,00,000.00");
  });

  it("handles null, undefined, or NaN gracefully in formatInr", () => {
    assert.strictEqual(formatInr(null), "—");
    assert.strictEqual(formatInr(undefined), "—");
    assert.strictEqual(formatInr(NaN), "—");
  });

  it("formats USD currency correctly", () => {
    assert.strictEqual(formatUsd(0), "$0.00");
    assert.strictEqual(formatUsd(12.3456), "$12.3456");
    assert.strictEqual(formatUsd(null), "—");
    assert.strictEqual(formatUsd(undefined), "—");
  });

  it("formats canonical service names to human-readable labels", () => {
    assert.strictEqual(formatServiceName("google_places"), "Places API (Discovery)");
    assert.strictEqual(formatServiceName("ai_analysis"), "AI Website Analysis");
    assert.strictEqual(formatServiceName("ai_classification"), "AI Reply Classification");
    assert.strictEqual(formatServiceName("ai_message_gen"), "AI Message Generator");
    assert.strictEqual(formatServiceName("whatsapp"), "WhatsApp Outreach");
    assert.strictEqual(formatServiceName("lighthouse"), "Lighthouse Web Audit");
    assert.strictEqual(formatServiceName("custom_billing_engine"), "Custom Billing Engine");
  });
});

describe("Analytics UI - Funnel Chart Logic", () => {
  const sampleFunnel = [
    { name: "Found", count: 100, conversion_rate: 100.0, overall_rate: 100.0 },
    { name: "Audited", count: 80, conversion_rate: 80.0, overall_rate: 80.0 },
    { name: "Qualified", count: 40, conversion_rate: 50.0, overall_rate: 40.0 },
    { name: "Contacted", count: 20, conversion_rate: 50.0, overall_rate: 20.0 },
    { name: "Replied", count: 10, conversion_rate: 50.0, overall_rate: 10.0 },
    { name: "Interested", count: 4, conversion_rate: 40.0, overall_rate: 4.0 },
    { name: "Won", count: 1, conversion_rate: 25.0, overall_rate: 1.0 },
    { name: "ZeroStep", count: 0, conversion_rate: 0.0, overall_rate: 0.0 },
  ];

  it("calculates bar width with minimum clamp for non-zero steps", () => {
    assert.strictEqual(calculateFunnelBarWidth(sampleFunnel[0]), 100.0);
    assert.strictEqual(calculateFunnelBarWidth(sampleFunnel[1]), 80.0);
    // When count > 0 but rate is 1.0, minimum visual width clamped at 3%
    assert.strictEqual(calculateFunnelBarWidth(sampleFunnel[6]), 3.0);
    // When count is 0, bar width is 0%
    assert.strictEqual(calculateFunnelBarWidth(sampleFunnel[7]), 0.0);
  });

  it("clamps extreme rates between 3% and 100% and handles non-finite inputs", () => {
    assert.strictEqual(calculateFunnelBarWidth({ count: 10, overall_rate: 150.0 }), 100.0);
    assert.strictEqual(calculateFunnelBarWidth({ count: 10, overall_rate: -10.0 }), 3.0);
    assert.strictEqual(calculateFunnelBarWidth({ count: 10, overall_rate: NaN }), 3.0);
    assert.strictEqual(calculateFunnelBarWidth({ count: 0, overall_rate: 100.0 }), 0.0);
  });

  it("verifies the 7-step canonical funnel sequence", () => {
    const canonicalNames = ["Found", "Audited", "Qualified", "Contacted", "Replied", "Interested", "Won"];
    const actualNames = sampleFunnel.slice(0, 7).map((s) => s.name);
    assert.deepStrictEqual(actualNames, canonicalNames);
  });
});

describe("Analytics UI - Outreach Rates & Safety Clamping", () => {
  it("clamps rates cleanly between 0 and 100%", () => {
    assert.strictEqual(clampRate(85.5), 85.5);
    assert.strictEqual(clampRate(0), 0);
    assert.strictEqual(clampRate(100), 100);
    assert.strictEqual(clampRate(120), 100);
    assert.strictEqual(clampRate(-5), 0);
    assert.strictEqual(clampRate(NaN), 0);
    assert.strictEqual(clampRate(undefined), 0);
    assert.strictEqual(clampRate(null), 0);
  });
});

describe("Analytics UI - Empty State Rule per UI-UX.md §6.11", () => {
  it("triggers empty state banner when has_sent_messages is false", () => {
    const kpisNoOutreach = {
      total_leads: 50,
      qualified_leads: 20,
      messages_sent: 0,
      total_replies: 0,
      interested_replies: 0,
      deals_won: 0,
      total_cost_inr: 45.0,
      cost_per_won_deal_inr: null,
      cost_per_qualified_lead_inr: 2.25,
      has_sent_messages: false,
    };
    assert.strictEqual(shouldShowEmptyState(kpisNoOutreach), true);
  });

  it("does not trigger empty state banner when has_sent_messages is true", () => {
    const kpisWithOutreach = {
      total_leads: 50,
      qualified_leads: 20,
      messages_sent: 12,
      total_replies: 4,
      interested_replies: 2,
      deals_won: 1,
      total_cost_inr: 120.0,
      cost_per_won_deal_inr: 120.0,
      cost_per_qualified_lead_inr: 6.0,
      has_sent_messages: true,
    };
    assert.strictEqual(shouldShowEmptyState(kpisWithOutreach), false);
  });

  it("triggers empty state banner when kpis is null or undefined", () => {
    assert.strictEqual(shouldShowEmptyState(null), true);
    assert.strictEqual(shouldShowEmptyState(undefined), true);
  });
});

describe("Analytics UI - Date Presets and Filters", () => {
  it("returns undefined dates for all_time preset", () => {
    const range = getDateRangeFromPreset("all_time");
    assert.strictEqual(range.from_date, undefined);
    assert.strictEqual(range.to_date, undefined);
  });

  it("returns ISO date bounds for last_7_days and last_30_days", () => {
    const r7 = getDateRangeFromPreset("last_7_days");
    assert.ok(r7.from_date);
    assert.ok(r7.to_date);
    const diffDays7 = Math.round((new Date(r7.to_date) - new Date(r7.from_date)) / 86400000);
    assert.strictEqual(diffDays7, 7);

    const r30 = getDateRangeFromPreset("last_30_days");
    assert.ok(r30.from_date);
    assert.ok(r30.to_date);
    const diffDays30 = Math.round((new Date(r30.to_date) - new Date(r30.from_date)) / 86400000);
    assert.strictEqual(diffDays30, 30);
  });
});

describe("Analytics UI - Cost Operations Aggregation & Endpoint Building", () => {
  it("accurately sums operations across services defensively", () => {
    const services = [
      { service: "google_places", api_calls: 15, cost_inr: 45.0, cost_usd: 0.54 },
      { service: "ai_analysis", api_calls: 10, cost_inr: 83.0, cost_usd: 1.0 },
      { service: "whatsapp", api_calls: 5, cost_inr: 4.15, cost_usd: 0.05 },
      { service: "unknown_corrupt", api_calls: null, cost_inr: 0, cost_usd: 0 },
    ];
    assert.strictEqual(calculateTotalOperations(services), 30);
    assert.strictEqual(calculateTotalOperations([]), 0);
    assert.strictEqual(calculateTotalOperations(null), 0);
  });

  it("builds safe, URI-encoded endpoints", () => {
    assert.strictEqual(buildAnalyticsEndpoint("all", ""), "/api/analytics/overview");
    assert.strictEqual(
      buildAnalyticsEndpoint("c7a10be6-4444-42b7-a365-517b62fb1f10", "?from_date=2026-11-01"),
      "/api/analytics/campaign/c7a10be6-4444-42b7-a365-517b62fb1f10?from_date=2026-11-01"
    );
    assert.strictEqual(
      buildAnalyticsEndpoint("campaign with spaces", ""),
      "/api/analytics/campaign/campaign%20with%20spaces"
    );
  });
});
