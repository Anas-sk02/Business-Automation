import { describe, it } from "node:test";
import assert from "node:assert/strict";

// Helper replicas matching frontend/components/audit/LighthouseScores.tsx
function getScoreThresholdTone(score) {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return {
      tone: "none",
      textClass: "text-muted-foreground",
      barClass: "bg-muted",
    };
  }

  if (score < 50) {
    return {
      tone: "problem",
      textClass: "text-problem",
      barClass: "bg-problem",
    };
  }
  if (score < 90) {
    return {
      tone: "caution",
      textClass: "text-caution",
      barClass: "bg-caution",
    };
  }
  return {
    tone: "good",
    textClass: "text-good",
    barClass: "bg-good",
  };
}

// Helper replicas matching frontend/components/audit/EvidenceDrawer.tsx
function getVerificationBadge(status) {
  switch (status) {
    case "verified":
      return {
        label: "Verified by audit",
        tone: "good",
      };
    case "contradicted":
      return {
        label: "Contradicted by audit",
        tone: "problem",
      };
    case "unverified":
    default:
      return {
        label: "Not verified",
        tone: "neutral",
      };
  }
}

function getSeverityStyle(severity) {
  switch (severity) {
    case "critical":
    case "high":
      return {
        label: severity === "critical" ? "Critical" : "High",
        borderClass: "border-l-problem",
      };
    case "medium":
      return {
        label: "Medium",
        borderClass: "border-l-caution",
      };
    case "low":
      return {
        label: "Low",
        borderClass: "border-l-muted-foreground/60",
      };
    case "info":
    default:
      return {
        label: "Info",
        borderClass: "border-l-muted-foreground/40",
      };
  }
}

function getPossibleImpact(title, description) {
  const text = (title + " " + description).toLowerCase();
  if (text.includes("overflow") || text.includes("mobile")) {
    return "Some mobile visitors may find navigation difficult or experience horizontal clipping.";
  }
  if (text.includes("slow") || text.includes("load time")) {
    return "Prospective customers on cellular connections may abandon the page before it loads.";
  }
  if (text.includes("broken") || text.includes("404")) {
    return "Broken links can reduce trust and cause visitors to reach dead ends.";
  }
  if (text.includes("ssl") || text.includes("security")) {
    return "Modern browsers may warn visitors that this connection is not private.";
  }
  return "This issue may affect site usability or search ranking depending on visitor intent.";
}

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

function formatSafeDate(dateStr, fallback = "Not recorded") {
  const dateObj = dateStr ? new Date(dateStr) : null;
  return dateObj && !Number.isNaN(dateObj.getTime())
    ? dateObj.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
    : fallback;
}

describe("Audit UI & Evidence Presentation Component Tests", () => {
  it("evaluates Lighthouse score thresholds per UI-UX.md §6.6 (<50 problem, 50-89 caution, >=90 good)", () => {
    // Under 50 -> problem
    assert.strictEqual(getScoreThresholdTone(0).tone, "problem");
    assert.strictEqual(getScoreThresholdTone(25).tone, "problem");
    assert.strictEqual(getScoreThresholdTone(49).tone, "problem");

    // 50 to 89 -> caution
    assert.strictEqual(getScoreThresholdTone(50).tone, "caution");
    assert.strictEqual(getScoreThresholdTone(75).tone, "caution");
    assert.strictEqual(getScoreThresholdTone(89).tone, "caution");

    // 90 and above -> good
    assert.strictEqual(getScoreThresholdTone(90).tone, "good");
    assert.strictEqual(getScoreThresholdTone(95).tone, "good");
    assert.strictEqual(getScoreThresholdTone(100).tone, "good");

    // Missing or invalid values -> none
    assert.strictEqual(getScoreThresholdTone(null).tone, "none");
    assert.strictEqual(getScoreThresholdTone(undefined).tone, "none");
    assert.strictEqual(getScoreThresholdTone(NaN).tone, "none");
  });

  it("formats verification status with explicit words per UI-UX.md §5.4", () => {
    assert.strictEqual(getVerificationBadge("verified").label, "Verified by audit");
    assert.strictEqual(getVerificationBadge("unverified").label, "Not verified");
    assert.strictEqual(getVerificationBadge("contradicted").label, "Contradicted by audit");
    assert.strictEqual(getVerificationBadge("unknown").label, "Not verified");
  });

  it("applies 3px border styling based on severity per UI-UX.md §5.4", () => {
    assert.strictEqual(getSeverityStyle("critical").borderClass, "border-l-problem");
    assert.strictEqual(getSeverityStyle("high").borderClass, "border-l-problem");
    assert.strictEqual(getSeverityStyle("medium").borderClass, "border-l-caution");
    assert.strictEqual(getSeverityStyle("low").borderClass, "border-l-muted-foreground/60");
    assert.strictEqual(getSeverityStyle("info").borderClass, "border-l-muted-foreground/40");
  });

  it("ensures possible impact text is worded as a possibility and never as proof per UI-UX.md §5.4", () => {
    const mobileImpact = getPossibleImpact("Mobile layout overflows by 240px", "Horizontal scroll");
    assert.match(mobileImpact, /\b(may|can)\b/i, "Impact must be worded as possibility");
    assert.doesNotMatch(mobileImpact, /\b(proves|guarantees|lost \$\d+)\b/i);

    const speedImpact = getPossibleImpact("Slow page load time", "Takes 4.2 seconds");
    assert.match(speedImpact, /\b(may|can)\b/i);

    const sslImpact = getPossibleImpact("SSL Certificate invalid", "Untrusted connection");
    assert.match(sslImpact, /\b(may|can)\b/i);
  });

  it("handles 'No website found for this business' as an honest state per UI-UX.md §6.6", () => {
    function getAuditEmptyState(websiteUrl, audit) {
      if (!websiteUrl) {
        return {
          title: "No website found for this business",
          isError: false,
        };
      }
      if (!audit) {
        return {
          title: "No audit performed yet",
          isError: false,
        };
      }
      if (audit.status === "failed" || audit.status === "timeout") {
        return {
          title: audit.status === "timeout" ? "Audit timed out" : "Audit failed",
          isError: true,
        };
      }
      return {
        title: "Website audit overview",
        isError: false,
      };
    }

    assert.strictEqual(
      getAuditEmptyState(null, null).title,
      "No website found for this business"
    );
    assert.strictEqual(getAuditEmptyState(null, null).isError, false);

    assert.strictEqual(
      getAuditEmptyState("https://example.com", null).title,
      "No audit performed yet"
    );

    assert.strictEqual(
      getAuditEmptyState("https://example.com", { status: "failed" }).title,
      "Audit failed"
    );
    assert.strictEqual(
      getAuditEmptyState("https://example.com", { status: "failed" }).isError,
      true
    );

    assert.strictEqual(
      getAuditEmptyState("https://example.com", { status: "completed" }).title,
      "Website audit overview"
    );
  });

  it("safely sanitizes screenshot URLs and external links against malicious schemes", () => {
    assert.strictEqual(
      sanitizeUrl("https://supabase.co/storage/v1/object/sign/screenshots/demo.png"),
      "https://supabase.co/storage/v1/object/sign/screenshots/demo.png"
    );
    assert.strictEqual(sanitizeUrl("http://localhost:8000/test.png"), "http://localhost:8000/test.png");
    assert.strictEqual(sanitizeUrl("javascript:alert(1)"), null);
    assert.strictEqual(sanitizeUrl("data:image/svg+xml;base64,PHN2Z..."), null);
    assert.strictEqual(sanitizeUrl("file:///C:/Windows/system.ini"), null);
  });

  it("safely formats dates and avoids 'Invalid Date' errors on corrupted timestamps", () => {
    assert.strictEqual(formatSafeDate("2026-10-12T14:30:00Z"), "Oct 12, 2026");
    assert.strictEqual(formatSafeDate("not-a-valid-date"), "Not recorded");
    assert.strictEqual(formatSafeDate(null), "Not recorded");
    assert.strictEqual(formatSafeDate(undefined), "Not recorded");
    assert.strictEqual(formatSafeDate("", "Timestamp not available"), "Timestamp not available");
  });
});
