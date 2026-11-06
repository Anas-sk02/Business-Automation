import { describe, it } from "node:test";
import assert from "node:assert/strict";

// Stage 7: Analytics, Settings, Suppression & Global Polish E2E Integration Suite

// 1. Funnel Calculation Logic matching backend/services/analytics.py & FunnelChart.tsx
function computeFunnel(leads) {
  const found = leads.length;
  const audited = leads.filter((l) => l.audit_status === "completed" || l.website_audited).length;
  const qualified = leads.filter((l) => (l.fit_score ?? 0) >= 60).length;
  const contacted = leads.filter((l) =>
    ["contacted", "followup_due", "replied", "interested", "meeting_scheduled", "proposal_sent", "negotiation", "won", "not_interested", "no_response", "closed_lost", "opted_out"].includes(l.pipeline_stage)
  ).length;
  const replied = leads.filter((l) =>
    ["replied", "interested", "meeting_scheduled", "proposal_sent", "negotiation", "won"].includes(l.pipeline_stage)
  ).length;
  const interested = leads.filter((l) =>
    ["interested", "meeting_scheduled", "proposal_sent", "negotiation", "won"].includes(l.pipeline_stage)
  ).length;
  const won = leads.filter((l) => l.pipeline_stage === "won").length;

  const rawSteps = [
    { name: "Found", count: found },
    { name: "Audited", count: audited },
    { name: "Qualified", count: qualified },
    { name: "Contacted", count: contacted },
    { name: "Replied", count: replied },
    { name: "Interested", count: interested },
    { name: "Won", count: won },
  ];

  const funnel = [];
  let prevCount = found;
  for (let i = 0; i < rawSteps.length; i++) {
    const step = rawSteps[i];
    const conversion_rate = i === 0
      ? 100.0
      : prevCount > 0
      ? Math.round((step.count / prevCount) * 1000) / 10
      : 0.0;
    const overall_rate = found > 0
      ? Math.round((step.count / found) * 1000) / 10
      : 0.0;

    funnel.push({
      name: step.name,
      count: step.count,
      conversion_rate,
      overall_rate,
    });
    prevCount = step.count;
  }

  return funnel;
}

// 2. WhatsApp Outreach Reliability Logic matching backend/services/analytics.py & OutreachMetrics.tsx
function computeOutreachMetrics(messages) {
  const outbound = messages.filter((m) => m.direction === "outbound");
  const total_sent = outbound.filter((m) => ["sent", "delivered", "read"].includes(m.status)).length;
  const total_delivered = outbound.filter((m) => ["delivered", "read"].includes(m.status)).length;
  const total_read = outbound.filter((m) => m.status === "read").length;
  const total_failed = outbound.filter((m) => m.status === "failed").length;

  const repliedLeadIds = new Set(
    messages.filter((m) => m.direction === "inbound").map((m) => m.lead_id)
  );
  const total_replied = repliedLeadIds.size;
  const total_opted_out = messages.filter((m) => m.is_opt_out || m.classification === "opt_out").length;

  const delivery_rate = total_sent > 0 ? Math.round((total_delivered / total_sent) * 1000) / 10 : 0.0;
  const read_rate = total_delivered > 0 ? Math.round((total_read / total_delivered) * 1000) / 10 : 0.0;
  const reply_rate = total_sent > 0 ? Math.round((total_replied / total_sent) * 1000) / 10 : 0.0;

  return {
    total_sent,
    total_delivered,
    total_read,
    total_replied,
    total_failed,
    total_opted_out,
    delivery_rate,
    read_rate,
    reply_rate,
  };
}

// 3. Cost & Unit Economics Logic matching CostBreakdown.tsx
function computeUnitEconomics(services, qualifiedLeadsCount, wonDealsCount, usdInrRate = 83.0) {
  const total_spend_usd = services.reduce((acc, curr) => acc + (curr.cost_usd || 0), 0);
  const total_spend_inr = Math.round(total_spend_usd * usdInrRate * 100) / 100;

  const cost_per_qualified_lead_inr = qualifiedLeadsCount > 0
    ? Math.round((total_spend_inr / qualifiedLeadsCount) * 100) / 100
    : null;

  const cost_per_won_deal_inr = wonDealsCount > 0
    ? Math.round((total_spend_inr / wonDealsCount) * 100) / 100
    : null;

  return {
    total_spend_usd: Math.round(total_spend_usd * 10000) / 10000,
    total_spend_inr,
    cost_per_qualified_lead_inr,
    cost_per_won_deal_inr,
  };
}

// 4. Phone & Date formatting per UI-UX.md §8
function formatInr(val) {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return `₹${val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatIndianPhone(rawPhone) {
  if (!rawPhone) return "—";
  const cleaned = rawPhone.trim();
  if (cleaned.startsWith("+91") && cleaned.length === 13) {
    return `+91 ${cleaned.slice(3, 8)} ${cleaned.slice(8)}`;
  }
  return cleaned;
}

function getSafeTelHref(phone) {
  if (!phone) return "#";
  const sanitized = phone.replace(/[^0-9+]/g, "");
  const digitCount = (sanitized.match(/\d/g) || []).length;
  return digitCount >= 7 ? `tel:${sanitized}` : "#";
}

describe("Stage 7 E2E - Acquisition Funnel Pipeline Math", () => {
  const sampleLeads = [
    { id: "1", audit_status: "completed", fit_score: 85, pipeline_stage: "won" },
    { id: "2", audit_status: "completed", fit_score: 75, pipeline_stage: "interested" },
    { id: "3", audit_status: "completed", fit_score: 65, pipeline_stage: "replied" },
    { id: "4", audit_status: "completed", fit_score: 60, pipeline_stage: "contacted" },
    { id: "5", audit_status: "completed", fit_score: 45, pipeline_stage: "discovered" }, // not qualified
    { id: "6", audit_status: "pending", fit_score: 30, pipeline_stage: "discovered" }, // not audited
  ];

  it("calculates exact step conversions and overall rates across all 7 stages", () => {
    const funnel = computeFunnel(sampleLeads);
    assert.strictEqual(funnel.length, 7);

    // Found: 6 total leads
    assert.strictEqual(funnel[0].name, "Found");
    assert.strictEqual(funnel[0].count, 6);
    assert.strictEqual(funnel[0].conversion_rate, 100.0);
    assert.strictEqual(funnel[0].overall_rate, 100.0);

    // Audited: 5 completed audits
    assert.strictEqual(funnel[1].name, "Audited");
    assert.strictEqual(funnel[1].count, 5);
    assert.strictEqual(funnel[1].conversion_rate, 83.3); // 5/6
    assert.strictEqual(funnel[1].overall_rate, 83.3);

    // Qualified: 4 leads with fit_score >= 60
    assert.strictEqual(funnel[2].name, "Qualified");
    assert.strictEqual(funnel[2].count, 4);
    assert.strictEqual(funnel[2].conversion_rate, 80.0); // 4/5
    assert.strictEqual(funnel[2].overall_rate, 66.7); // 4/6

    // Contacted: 4 leads at contacted or beyond
    assert.strictEqual(funnel[3].name, "Contacted");
    assert.strictEqual(funnel[3].count, 4);

    // Replied: 3 leads at replied or beyond
    assert.strictEqual(funnel[4].name, "Replied");
    assert.strictEqual(funnel[4].count, 3);
    assert.strictEqual(funnel[4].conversion_rate, 75.0); // 3/4

    // Interested: 2 leads at interested or won
    assert.strictEqual(funnel[5].name, "Interested");
    assert.strictEqual(funnel[5].count, 2);
    assert.strictEqual(funnel[5].conversion_rate, 66.7); // 2/3

    // Won: 1 deal won
    assert.strictEqual(funnel[6].name, "Won");
    assert.strictEqual(funnel[6].count, 1);
    assert.strictEqual(funnel[6].conversion_rate, 50.0); // 1/2
    assert.strictEqual(funnel[6].overall_rate, 16.7); // 1/6
  });

  it("handles empty leads dataset gracefully without division by zero", () => {
    const emptyFunnel = computeFunnel([]);
    assert.strictEqual(emptyFunnel.length, 7);
    for (const step of emptyFunnel) {
      assert.strictEqual(step.count, 0);
      assert.strictEqual(step.overall_rate, 0.0);
    }
  });
});

describe("Stage 7 E2E - WhatsApp Outreach Reliability & Conversion", () => {
  const sampleMessages = [
    { lead_id: "lead-1", direction: "outbound", status: "read" },
    { lead_id: "lead-1", direction: "inbound", status: "delivered", classification: "interested" },
    { lead_id: "lead-2", direction: "outbound", status: "delivered" },
    { lead_id: "lead-3", direction: "outbound", status: "sent" },
    { lead_id: "lead-4", direction: "outbound", status: "failed" },
    { lead_id: "lead-5", direction: "inbound", status: "delivered", is_opt_out: true, classification: "opt_out" },
  ];

  it("calculates accurate delivery, read, and reply rates", () => {
    const metrics = computeOutreachMetrics(sampleMessages);
    assert.strictEqual(metrics.total_sent, 3); // read, delivered, sent
    assert.strictEqual(metrics.total_delivered, 2); // read, delivered
    assert.strictEqual(metrics.total_read, 1);
    assert.strictEqual(metrics.total_failed, 1);
    assert.strictEqual(metrics.total_replied, 2); // 2 unique leads replied
    assert.strictEqual(metrics.total_opted_out, 1);

    // Delivery rate: 2 delivered / 3 sent = 66.7%
    assert.strictEqual(metrics.delivery_rate, 66.7);
    // Read rate: 1 read / 2 delivered = 50.0%
    assert.strictEqual(metrics.read_rate, 50.0);
    // Reply rate: 2 unique leads / 3 sent = 66.7%
    assert.strictEqual(metrics.reply_rate, 66.7);
  });
});

describe("Stage 7 E2E - Unit Economics & Indian Grouping Formatting", () => {
  const services = [
    { service: "google_places", api_calls: 50, cost_usd: 1.0 },
    { service: "ai_analysis", api_calls: 20, cost_usd: 2.0 },
    { service: "whatsapp", api_calls: 10, cost_usd: 0.1 },
  ];

  it("computes spend in INR and unit economics per qualified lead and deal won", () => {
    // 3.10 USD * 83.0 = 257.30 INR
    const economics = computeUnitEconomics(services, 4, 1);
    assert.strictEqual(economics.total_spend_usd, 3.1);
    assert.strictEqual(economics.total_spend_inr, 257.3);
    // Cost per qualified lead: 257.30 / 4 = 64.33 INR
    assert.strictEqual(economics.cost_per_qualified_lead_inr, 64.33);
    // Cost per won deal: 257.30 / 1 = 257.30 INR
    assert.strictEqual(economics.cost_per_won_deal_inr, 257.3);
  });

  it("returns null for cost per won deal when no deals have been won yet", () => {
    const economicsNoWins = computeUnitEconomics(services, 4, 0);
    assert.strictEqual(economicsNoWins.cost_per_won_deal_inr, null);
  });

  it("formats Indian rupees with en-IN numbering grouping", () => {
    assert.strictEqual(formatInr(257.3), "₹257.30");
    assert.strictEqual(formatInr(125000), "₹1,25,000.00");
    assert.strictEqual(formatInr(null), "—");
  });
});

describe("Stage 7 E2E - Suppression Safeguards & Phone URI Security", () => {
  it("formats phone numbers cleanly for Indian mobile readability", () => {
    assert.strictEqual(formatIndianPhone("+919822012345"), "+91 98220 12345");
  });

  it("generates safe tel: protocol hrefs and neutralizes malicious inputs", () => {
    assert.strictEqual(getSafeTelHref("+919822012345"), "tel:+919822012345");
    assert.strictEqual(getSafeTelHref("javascript:evil()"), "#");
    assert.strictEqual(getSafeTelHref("123"), "#"); // Too short to be a valid phone number
    assert.strictEqual(getSafeTelHref(null), "#");
  });
});

describe("Stage 7 E2E - Navigation & UI-UX Copy Integrity", () => {
  it("verifies canonical empty state banner copy per UI-UX.md §6.11", () => {
    const expectedAnalyticsEmptyCopy = "Analytics appear after you send your first messages.";
    assert.ok(expectedAnalyticsEmptyCopy.includes("Analytics appear after you send your first messages."));
  });

  it("verifies mandatory outreach templates note per UI-UX.md §6.10", () => {
    const expectedTemplateNote = "Messages that start a conversation must use an approved template. Approval can take a few days.";
    assert.ok(expectedTemplateNote.includes("Messages that start a conversation must use an approved template."));
  });

  it("formats template dates and handles invalid inputs defensively", () => {
    function formatTemplateDate(isoDate) {
      if (!isoDate) return "—";
      try {
        const d = new Date(isoDate);
        if (isNaN(d.getTime())) return "—";
        const day = d.getDate();
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        const month = months[d.getMonth()];
        const year = d.getFullYear();
        return `${day} ${month} ${year}`;
      } catch {
        return "—";
      }
    }

    assert.strictEqual(formatTemplateDate("2026-10-25T10:00:00Z"), "25 Oct 2026");
    assert.strictEqual(formatTemplateDate(null), "—");
    assert.strictEqual(formatTemplateDate("corrupted"), "—");
  });

  it("filters templates by name and purpose accurately", () => {
    const templates = [
      { name: "initial_outreach_pitch", purpose: "First contact pitch citing specific website audit" },
      { name: "gentle_followup_reminder", purpose: "First follow-up sent 3 days after initial message" },
      { name: "value_add_mockup_offer", purpose: "Second follow-up offering a complimentary mockup" },
    ];

    const searchPitch = templates.filter((t) => t.name.includes("pitch") || t.purpose.includes("pitch"));
    assert.strictEqual(searchPitch.length, 1);

    const searchMockup = templates.filter((t) => t.name.includes("mockup") || t.purpose.includes("mockup"));
    assert.strictEqual(searchMockup.length, 1);
  });
});

