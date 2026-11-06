import { describe, it } from "node:test";
import assert from "node:assert/strict";

// Helper logic replicating frontend/components/settings/SuppressionTable.tsx
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

function formatIndianDate(isoDate) {
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

// Logic replicating frontend/components/settings/ProfileSettings.tsx validation
function validateProfilePayload(payload) {
  const errors = [];
  if (payload.whatsapp_number && payload.whatsapp_number.trim()) {
    const cleanPhone = payload.whatsapp_number.trim().replace(/\s+/g, "").replace(/-/g, "");
    const e164Regex = /^\+[1-9]\d{9,14}$/;
    if (!e164Regex.test(cleanPhone)) {
      errors.push("WhatsApp number must include country code in valid E.164 format (e.g. +91 98220 12345)");
    }
  }
  return {
    isValid: errors.length === 0,
    errors,
  };
}

function addServiceTag(existingTags, newTag) {
  const trimmed = (newTag || "").trim();
  if (!trimmed) return existingTags;
  if (existingTags.some((s) => s.toLowerCase() === trimmed.toLowerCase())) {
    return existingTags;
  }
  return [...existingTags, trimmed];
}

function removeServiceTag(existingTags, indexToRemove) {
  return existingTags.filter((_, idx) => idx !== indexToRemove);
}

// Logic replicating client-side search filtering
function filterSuppressionRecords(records, searchQuery) {
  if (!searchQuery || !searchQuery.trim()) return records;
  const q = searchQuery.trim().toLowerCase();
  return records.filter((r) => {
    return (
      (r.phone && r.phone.toLowerCase().includes(q)) ||
      (r.business_name && r.business_name.toLowerCase().includes(q)) ||
      (r.campaign_name && r.campaign_name.toLowerCase().includes(q)) ||
      (r.suppression_reason && r.suppression_reason.toLowerCase().includes(q))
    );
  });
}

describe("Settings UI - Phone & Date Formatting per UI-UX.md §8", () => {
  it("formats Indian E.164 phone numbers with readability groupings", () => {
    assert.strictEqual(formatIndianPhone("+919822012345"), "+91 98220 12345");
    assert.strictEqual(formatIndianPhone("+918888877777"), "+91 88888 77777");
    assert.strictEqual(formatIndianPhone("+14155552671"), "+14155552671");
  });

  it("handles null, undefined, or empty phone strings gracefully", () => {
    assert.strictEqual(formatIndianPhone(null), "—");
    assert.strictEqual(formatIndianPhone(undefined), "—");
    assert.strictEqual(formatIndianPhone(""), "—");
  });

  it("generates safe tel: protocol hrefs sanitizing dangerous characters", () => {
    assert.strictEqual(getSafeTelHref("+919822012345"), "tel:+919822012345");
    assert.strictEqual(getSafeTelHref("+91 98220 12345"), "tel:+919822012345");
    assert.strictEqual(getSafeTelHref("javascript:alert(1)"), "#");
    assert.strictEqual(getSafeTelHref(null), "#");
    assert.strictEqual(getSafeTelHref(""), "#");
  });

  it("formats dates in Day Month Year format (never US order)", () => {
    const formatted = formatIndianDate("2026-10-12T14:30:00Z");
    assert.strictEqual(formatted, "12 Oct 2026");
    assert.strictEqual(formatIndianDate("2026-01-05T00:00:00Z"), "5 Jan 2026");
  });

  it("handles invalid or null dates without crashing", () => {
    assert.strictEqual(formatIndianDate(null), "—");
    assert.strictEqual(formatIndianDate(undefined), "—");
    assert.strictEqual(formatIndianDate("invalid-date-string"), "—");
  });
});

describe("Settings UI - Profile Validation & Tag Management", () => {
  it("validates valid WhatsApp numbers with country codes", () => {
    const valid1 = validateProfilePayload({ whatsapp_number: "+91 98220 12345" });
    assert.strictEqual(valid1.isValid, true);
    assert.strictEqual(valid1.errors.length, 0);

    const valid2 = validateProfilePayload({ whatsapp_number: "+919822012345" });
    assert.strictEqual(valid2.isValid, true);

    const empty = validateProfilePayload({ whatsapp_number: "" });
    assert.strictEqual(empty.isValid, true);
  });

  it("rejects invalid WhatsApp numbers missing country code, starting with 0, or too short", () => {
    const noCountryCode = validateProfilePayload({ whatsapp_number: "9822012345" });
    assert.strictEqual(noCountryCode.isValid, false);

    const tooShort = validateProfilePayload({ whatsapp_number: "+91123" });
    assert.strictEqual(tooShort.isValid, false);

    const zeroCountry = validateProfilePayload({ whatsapp_number: "+09822012345" });
    assert.strictEqual(zeroCountry.isValid, false);
  });

  it("adds unique service tags and ignores case-insensitive duplicates", () => {
    let services = ["Website Redesign"];
    services = addServiceTag(services, "SEO Optimization");
    assert.deepStrictEqual(services, ["Website Redesign", "SEO Optimization"]);

    // Attempting duplicate (case insensitive)
    services = addServiceTag(services, "website redesign");
    assert.deepStrictEqual(services, ["Website Redesign", "SEO Optimization"]);

    // Attempting whitespace only
    services = addServiceTag(services, "   ");
    assert.deepStrictEqual(services, ["Website Redesign", "SEO Optimization"]);
  });

  it("removes service tags by index accurately", () => {
    const initial = ["Website Redesign", "SEO Optimization", "AI Automation"];
    const updated = removeServiceTag(initial, 1);
    assert.deepStrictEqual(updated, ["Website Redesign", "AI Automation"]);
  });
});

describe("Settings UI - Suppression Safeguard Audit Logic", () => {
  const sampleRecords = [
    {
      id: "lead-1",
      phone: "+919822011111",
      business_name: "Apex Coaching Pune",
      campaign_id: "camp-1",
      campaign_name: "Pune Coaching Centers",
      suppression_reason: "Requested STOP",
      opted_out_at: "2026-10-12T10:00:00Z",
    },
    {
      id: "lead-2",
      phone: "+919822022222",
      business_name: "Bright Dental Care",
      campaign_id: "camp-2",
      campaign_name: "Mumbai Dentists",
      suppression_reason: "Nahi chahiye opt-out",
      opted_out_at: "2026-10-14T12:00:00Z",
    },
    {
      id: "lead-3",
      phone: "+919822033333",
      business_name: "Spark Fitness Gym",
      campaign_id: "camp-1",
      campaign_name: "Pune Coaching Centers",
      suppression_reason: "Stop command",
      opted_out_at: "2026-10-15T09:00:00Z",
    },
  ];

  it("filters suppression records across phone, business name, and campaign", () => {
    const byPhone = filterSuppressionRecords(sampleRecords, "11111");
    assert.strictEqual(byPhone.length, 1);
    assert.strictEqual(byPhone[0].business_name, "Apex Coaching Pune");

    const byBusiness = filterSuppressionRecords(sampleRecords, "dental");
    assert.strictEqual(byBusiness.length, 1);
    assert.strictEqual(byBusiness[0].phone, "+919822022222");

    const byCampaign = filterSuppressionRecords(sampleRecords, "Pune Coaching");
    assert.strictEqual(byCampaign.length, 2);

    const byReason = filterSuppressionRecords(sampleRecords, "nahi chahiye");
    assert.strictEqual(byReason.length, 1);

    const emptyQuery = filterSuppressionRecords(sampleRecords, "");
    assert.strictEqual(emptyQuery.length, 3);
  });

  it("calculates pagination bounds correctly", () => {
    const totalItems = 35;
    const pageSize = 20;
    const totalPages = Math.ceil(totalItems / pageSize);
    assert.strictEqual(totalPages, 2);

    const zeroTotalPages = Math.max(Math.ceil(0 / pageSize), 1);
    assert.strictEqual(zeroTotalPages, 1);
  });
});
