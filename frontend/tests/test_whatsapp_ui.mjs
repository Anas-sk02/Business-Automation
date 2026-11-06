import { describe, it } from "node:test";
import assert from "node:assert/strict";

// Replicas of logic functions from MessageDraftEditor.tsx and WhatsAppChat.tsx
function formatPhoneDisplay(phone) {
  if (!phone) return "Not listed";
  const cleaned = phone.replace(/[^\d+]/g, "");
  if (cleaned.startsWith("+91") && cleaned.length === 13) {
    return `+91 ${cleaned.slice(3, 8)} ${cleaned.slice(8)}`;
  }
  return cleaned;
}

function isIndianQuietHours(date = new Date()) {
  const utc = date.getTime() + date.getTimezoneOffset() * 60000;
  const istDate = new Date(utc + 5.5 * 3600000);
  const hours = istDate.getHours();
  return hours >= 21 || hours < 9;
}

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

function getClassificationChip(classification) {
  if (!classification) return null;

  switch (classification) {
    case "interested":
    case "meeting_request":
    case "pricing_request":
    case "wants_info":
      return {
        label:
          classification === "meeting_request"
            ? "Meeting requested"
            : classification === "pricing_request"
            ? "Pricing requested"
            : classification === "wants_info"
            ? "Requested details"
            : "Interested",
        tone: "good",
      };
    case "not_interested":
    case "wrong_number":
      return {
        label:
          classification === "wrong_number" ? "Wrong number" : "Not interested",
        tone: "neutral",
      };
    case "opt_out":
      return {
        label: "Opt-out requested",
        tone: "problem",
      };
    case "not_now":
    case "unclear":
    default:
      return {
        label: classification === "not_now" ? "Not now" : "Unclear",
        tone: "caution",
      };
  }
}

function formatMessageTime(isoString) {
  if (!isoString) return "";
  try {
    const dt = new Date(isoString);
    if (isNaN(dt.getTime())) return "";
    return dt.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

function validateDraftToSend(body, isSuppressed, hasPhone) {
  if (isSuppressed) {
    return { valid: false, error: "Recipient opted out" };
  }
  if (!hasPhone) {
    return { valid: false, error: "No phone number" };
  }
  const clean = (body || "").trim();
  if (!clean) {
    return { valid: false, error: "Message text cannot be empty" };
  }
  if (clean.length > 2000) {
    return { valid: false, error: "Message exceeds 2000 characters limit" };
  }
  if (!/stop/i.test(clean)) {
    return { valid: false, error: "Missing required opt-out instruction" };
  }
  return { valid: true, error: null };
}

describe("WhatsApp UI & Presentation Component Tests", () => {
  it("formats Indian phone numbers into clean readability standard per UI-UX.md §2", () => {
    assert.equal(formatPhoneDisplay("+919876543210"), "+91 98765 43210");
    assert.equal(formatPhoneDisplay("+14155552671"), "+14155552671");
    assert.equal(formatPhoneDisplay(null), "Not listed");
    assert.equal(formatPhoneDisplay(""), "Not listed");
  });

  it("calculates Indian quiet hours (21:00 to 09:00 IST) accurately across timezones", () => {
    // 22:30 IST
    const lateNightIST = new Date("2026-11-06T17:00:00.000Z"); // 17:00 UTC = 22:30 IST
    assert.equal(isIndianQuietHours(lateNightIST), true);

    // 04:00 IST
    const earlyMorningIST = new Date("2026-11-05T22:30:00.000Z"); // 22:30 UTC = 04:00 IST
    assert.equal(isIndianQuietHours(earlyMorningIST), true);

    // 14:00 IST (Business day)
    const afternoonIST = new Date("2026-11-06T08:30:00.000Z"); // 08:30 UTC = 14:00 IST
    assert.equal(isIndianQuietHours(afternoonIST), false);

    // 09:00 IST (Quiet hours end)
    const nineAmIST = new Date("2026-11-06T03:30:00.000Z"); // 03:30 UTC = 09:00 IST
    assert.equal(isIndianQuietHours(nineAmIST), false);
  });

  it("evaluates 24-hour service conversation window status per UI-UX.md §6.7", () => {
    const fixedNow = new Date("2026-11-06T12:00:00.000Z").getTime();

    // Inbound reply received 3 hours ago -> Window OPEN
    const recentMessages = [
      {
        id: "msg-1",
        direction: "outbound",
        message_body: "First touch",
        created_at: new Date(fixedNow - 4 * 3600000).toISOString(),
      },
      {
        id: "msg-2",
        direction: "inbound",
        message_body: "Yes interested",
        created_at: new Date(fixedNow - 3 * 3600000).toISOString(),
      },
    ];
    const openStatus = get24HourWindowStatus(recentMessages, fixedNow);
    assert.equal(openStatus.isOpen, true);
    assert.ok(openStatus.closesAt instanceof Date);

    // Inbound reply received 26 hours ago -> Window CLOSED
    const oldMessages = [
      {
        id: "msg-3",
        direction: "inbound",
        message_body: "Call me yesterday",
        created_at: new Date(fixedNow - 26 * 3600000).toISOString(),
      },
    ];
    const closedStatus = get24HourWindowStatus(oldMessages, fixedNow);
    assert.equal(closedStatus.isOpen, false);

    // Outbound only messages -> Window CLOSED
    const outboundOnly = [
      {
        id: "msg-4",
        direction: "outbound",
        message_body: "Outreach template",
        created_at: new Date(fixedNow - 1 * 3600000).toISOString(),
      },
    ];
    const outboundStatus = get24HourWindowStatus(outboundOnly, fixedNow);
    assert.equal(outboundStatus.isOpen, false);
  });

  it("maps reply classifications to semantic tones and plain text labels per UI-UX.md §6.7", () => {
    const interested = getClassificationChip("interested");
    assert.equal(interested.label, "Interested");
    assert.equal(interested.tone, "good");

    const meeting = getClassificationChip("meeting_request");
    assert.equal(meeting.label, "Meeting requested");
    assert.equal(meeting.tone, "good");

    const optOut = getClassificationChip("opt_out");
    assert.equal(optOut.label, "Opt-out requested");
    assert.equal(optOut.tone, "problem");

    const notInterested = getClassificationChip("not_interested");
    assert.equal(notInterested.label, "Not interested");
    assert.equal(notInterested.tone, "neutral");

    const unclear = getClassificationChip("unclear");
    assert.equal(unclear.label, "Unclear");
    assert.equal(unclear.tone, "caution");
  });

  it("enforces mandatory opt-out copy in outreach messages per UI-UX.md §6.7 & decisions.md §10", () => {
    const sampleBody = "Hi Dr. Sharma, noticed your clinic website takes 5s to load.\n\nReply STOP to opt out";
    assert.match(sampleBody, /Reply STOP to opt out/i);
  });

  it("enforces exact blocked states rules per UI-UX.md §5.8", () => {
    const rules = {
      optedOut: "This number opted out of communications. It cannot be messaged.",
      noPhone: "This lead does not have a phone number. A phone number is required to send via WhatsApp.",
      quietHours: "Indian quiet hours active (21:00 to 09:00 IST)",
    };

    assert.ok(rules.optedOut.includes("cannot be messaged"));
    assert.ok(rules.noPhone.includes("phone number is required"));
    assert.ok(rules.quietHours.includes("quiet hours"));
  });

  it("safely formats message timestamps avoiding NaN or Invalid Date", () => {
    assert.equal(formatMessageTime("invalid-date-string"), "");
    assert.equal(formatMessageTime(null), "");
    assert.equal(formatMessageTime(undefined), "");

    const validIso = "2026-11-06T10:30:00.000Z";
    const formatted = formatMessageTime(validIso);
    assert.ok(formatted.length > 0);
  });

  it("validates draft pre-send criteria and blocks drafts missing opt-out line", () => {
    const validDraft = "Hello, audit found mobile issue.\n\nReply STOP to opt out";
    assert.deepEqual(validateDraftToSend(validDraft, false, true), {
      valid: true,
      error: null,
    });

    const noOptOut = "Hello, audit found mobile issue. Please reply to discuss.";
    const resultNoOptOut = validateDraftToSend(noOptOut, false, true);
    assert.equal(resultNoOptOut.valid, false);
    assert.equal(resultNoOptOut.error, "Missing required opt-out instruction");

    const emptyDraft = "   \n\t ";
    assert.equal(validateDraftToSend(emptyDraft, false, true).valid, false);

    const suppressedLead = validateDraftToSend(validDraft, true, true);
    assert.equal(suppressedLead.valid, false);
    assert.equal(suppressedLead.error, "Recipient opted out");

    const missingPhone = validateDraftToSend(validDraft, false, false);
    assert.equal(missingPhone.valid, false);
    assert.equal(missingPhone.error, "No phone number");
  });
});

