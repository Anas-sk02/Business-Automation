import { describe, it, before } from "node:test";
import assert from "node:assert/strict";

const SUPABASE_URL = "https://pfccofklivdxncpeabln.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmY2NvZmtsaXZkeG5jcGVhYmxuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTMwOTc4MDksImV4cCI6MjEwODY3MzgwOX0.jMdhWVafB5atMXtMvkaohLilz0Ezouh_F2clsW2S1bI";
const BACKEND_URL = "http://127.0.0.1:8000";
const FRONTEND_URL = "http://127.0.0.1:3000";

const TEST_EMAIL = "mdanas12.2007@gmail.com";
const TEST_PASSWORD = "Anas1234";

let authToken = "";
let currentUserId = "";

describe("Stage 7 Real User Live Testing against Running App", () => {
  before(async () => {
    // 1. Authenticate with Supabase password grant
    const authRes = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
      method: "POST",
      headers: {
        apikey: SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: TEST_EMAIL,
        password: TEST_PASSWORD,
      }),
    });

    assert.strictEqual(authRes.status, 200, "Supabase authentication must succeed");
    const authData = await authRes.json();
    authToken = authData.access_token;
    currentUserId = authData.user.id;
    assert.ok(authToken, "Auth token must be non-empty");
    assert.ok(currentUserId, "Current user ID must be present");
  });

  // Feature 1: User Profile Settings & Identity (UI-UX.md §6.12)
  describe("1. Profile Settings API & Form Validation", () => {
    it("fetches the authenticated user profile (normal case)", async () => {
      const res = await fetch(`${BACKEND_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      assert.strictEqual(res.status, 200);
      const json = await res.json();
      assert.ok(json.data);
      assert.strictEqual(json.data.id, currentUserId);
      assert.strictEqual(json.data.email, TEST_EMAIL);
      assert.ok(Array.isArray(json.data.service_descriptions));
    });

    it("updates profile with valid details and service tags (normal case)", async () => {
      const updatePayload = {
        full_name: "Mohammad Anas Ajaz",
        company_name: "Apex Digital Solutions",
        whatsapp_number: "+919822012345",
        service_descriptions: ["Website Development", "SEO Audit", "AI Automation"],
        timezone: "Asia/Kolkata",
      };

      const res = await fetch(`${BACKEND_URL}/api/auth/profile`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${authToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(updatePayload),
      });

      assert.strictEqual(res.status, 200);
      const json = await res.json();
      assert.strictEqual(json.data.full_name, "Mohammad Anas Ajaz");
      assert.strictEqual(json.data.company_name, "Apex Digital Solutions");
      assert.strictEqual(json.data.whatsapp_number, "+919822012345");
      assert.deepStrictEqual(json.data.service_descriptions, [
        "Website Development",
        "SEO Audit",
        "AI Automation",
      ]);
    });

    it("rejects invalid WhatsApp number format (wrong input case)", async () => {
      const badPhonePayload = {
        whatsapp_number: "invalid-phone-without-country-code",
      };

      const res = await fetch(`${BACKEND_URL}/api/auth/profile`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${authToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(badPhonePayload),
      });

      assert.strictEqual(res.status, 422, "Should return 422 Unprocessable Entity for invalid phone format");
    });

    it("rejects invalid IANA timezone (wrong input case)", async () => {
      const badTzPayload = {
        timezone: "Mars/Olympus_Mons",
      };

      const res = await fetch(`${BACKEND_URL}/api/auth/profile`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${authToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(badTzPayload),
      });

      assert.strictEqual(res.status, 422, "Should return 422 Unprocessable Entity for invalid timezone");
    });

    it("rejects empty payload without fields to update (empty input case)", async () => {
      const res = await fetch(`${BACKEND_URL}/api/auth/profile`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${authToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });

      assert.strictEqual(res.status, 400, "Should return 400 Bad Request when no fields provided");
    });
  });

  // Feature 2: Analytics Overview & 7-Stage Funnel (UI-UX.md §6.11)
  describe("2. Analytics Overview & Funnel Calculations", () => {
    it("fetches overall analytics overview (normal case)", async () => {
      const res = await fetch(`${BACKEND_URL}/api/analytics/overview`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      assert.strictEqual(res.status, 200);
      const json = await res.json();
      assert.ok(json.data);

      const { kpis, funnel, messaging, costs, has_sent_messages } = json.data;

      // KPIs structure verification
      assert.ok(typeof kpis.total_leads_found === "number");
      assert.ok(typeof kpis.total_qualified === "number");
      assert.ok(typeof kpis.total_messages_sent === "number");
      assert.ok(typeof kpis.total_spend_inr === "number");

      // 7-step canonical funnel verification per UI-UX.md §6.11
      assert.strictEqual(funnel.length, 7);
      const expectedSteps = ["Found", "Audited", "Qualified", "Contacted", "Replied", "Interested", "Won"];
      assert.deepStrictEqual(funnel.map((s) => s.name), expectedSteps);

      // Funnel percentages non-negative and properly bounded
      for (const step of funnel) {
        assert.ok(step.count >= 0);
        assert.ok(step.conversion_rate >= 0 && step.conversion_rate <= 100);
        assert.ok(step.overall_rate >= 0 && step.overall_rate <= 100);
      }

      // Messaging reliability metrics
      assert.ok(messaging.delivery_rate >= 0 && messaging.delivery_rate <= 100);
      assert.ok(messaging.read_rate >= 0 && messaging.read_rate <= 100);
      assert.ok(messaging.reply_rate >= 0 && messaging.reply_rate <= 100);

      // Cost metrics
      assert.ok(costs.total_spend_inr >= 0);
      assert.ok(costs.total_spend_usd >= 0);
      assert.ok(Array.isArray(costs.services));

      // Empty state condition consistency
      if (kpis.total_messages_sent === 0) {
        assert.strictEqual(has_sent_messages, false);
      }
    });

    it("filters analytics by date range (normal case: last 30 days)", async () => {
      const now = new Date();
      const past30 = new Date(now.getTime() - 30 * 86400000);
      const from_date = past30.toISOString();
      const to_date = now.toISOString();

      const res = await fetch(
        `${BACKEND_URL}/api/analytics/overview?from_date=${encodeURIComponent(from_date)}&to_date=${encodeURIComponent(to_date)}`,
        { headers: { Authorization: `Bearer ${authToken}` } }
      );
      assert.strictEqual(res.status, 200);
      const json = await res.json();
      assert.ok(json.data.funnel);
    });

    it("rejects inverted date bounds from_date > to_date (wrong input case)", async () => {
      const res = await fetch(
        `${BACKEND_URL}/api/analytics/overview?from_date=2026-11-20T00:00:00Z&to_date=2026-11-01T00:00:00Z`,
        { headers: { Authorization: `Bearer ${authToken}` } }
      );
      assert.strictEqual(res.status, 400, "Should return 400 Bad Request for inverted date range");
      const json = await res.json();
      assert.ok(
        json.detail.includes("from_date cannot be later than to_date") ||
        json.detail.includes("from_date must not be after to_date")
      );
    });
  });

  // Feature 3: Campaign-Scoped Analytics & Cost Breakdown
  describe("3. Campaign-Scoped Analytics & Boundaries", () => {
    let campaignId = "";

    before(async () => {
      const res = await fetch(`${BACKEND_URL}/api/campaigns`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.status === 200) {
        const json = await res.json();
        if (json.data && json.data.length > 0) {
          campaignId = json.data[0].id;
        }
      }
    });

    it("fetches campaign-specific analytics if campaign exists (normal case)", async () => {
      if (!campaignId) return; // Skip if user has 0 campaigns
      const res = await fetch(`${BACKEND_URL}/api/analytics/campaign/${campaignId}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      assert.strictEqual(res.status, 200);
      const json = await res.json();
      assert.strictEqual(json.data.campaign_id, campaignId);
      assert.ok(json.data.funnel);
    });

    it("returns 404 for non-existent unowned campaign UUID (boundary case)", async () => {
      const unownedId = "00000000-0000-0000-0000-000000000000";
      const res = await fetch(`${BACKEND_URL}/api/analytics/campaign/${unownedId}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      assert.strictEqual(res.status, 404, "Must return 404 Not Found to prevent leaking existence");
    });

    it("returns 404 for invalid non-UUID identifier (wrong input case)", async () => {
      const res = await fetch(`${BACKEND_URL}/api/analytics/campaign/not-a-valid-uuid`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      assert.strictEqual(res.status, 404);
    });

    it("fetches service cost overview (normal case)", async () => {
      const res = await fetch(`${BACKEND_URL}/api/analytics/costs`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      assert.strictEqual(res.status, 200);
      const json = await res.json();
      assert.ok(Array.isArray(json.data.services));
      assert.ok(json.data.total_spend_inr >= 0);
    });
  });

  // Feature 4: Suppression Safeguard List (UI-UX.md §6.12 & decisions.md §10)
  describe("4. Suppression Safeguard Audit List", () => {
    it("fetches the suppression list (normal case)", async () => {
      const res = await fetch(`${BACKEND_URL}/api/settings/suppression-list?page=1&page_size=20`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      assert.strictEqual(res.status, 200);
      const json = await res.json();
      assert.ok(json.data);
      assert.ok(Array.isArray(json.data.suppressed_contacts));
      assert.ok(typeof json.data.total === "number");
      assert.strictEqual(json.data.page, 1);
      assert.strictEqual(json.data.page_size, 20);

      // Verify records structure
      for (const rec of json.data.suppressed_contacts) {
        assert.ok(rec.id);
        assert.ok(rec.phone);
        assert.ok(rec.campaign_id);
        assert.ok(rec.campaign_name);
        assert.ok(rec.opted_out_at);
      }
    });

    it("filters suppression records by search query (normal search case)", async () => {
      const res = await fetch(
        `${BACKEND_URL}/api/settings/suppression-list?search=nonexistent_contact_query_xyz`,
        { headers: { Authorization: `Bearer ${authToken}` } }
      );
      assert.strictEqual(res.status, 200);
      const json = await res.json();
      assert.strictEqual(json.data.suppressed_contacts.length, 0);
      assert.strictEqual(json.data.total, 0);
    });

    it("handles pagination beyond total records (empty page case)", async () => {
      const res = await fetch(
        `${BACKEND_URL}/api/settings/suppression-list?page=9999&page_size=20`,
        { headers: { Authorization: `Bearer ${authToken}` } }
      );
      assert.strictEqual(res.status, 200);
      const json = await res.json();
      assert.strictEqual(json.data.suppressed_contacts.length, 0);
    });
  });

  // Feature 5: Multi-Tenant Security & Access Control
  describe("5. Multi-Tenant Isolation & Unauthenticated Rejection", () => {
    it("rejects unauthenticated requests to /api/analytics/overview", async () => {
      const res = await fetch(`${BACKEND_URL}/api/analytics/overview`);
      assert.strictEqual(res.status, 401, "Must reject without Bearer token");
    });

    it("rejects invalid Bearer tokens to /api/settings/suppression-list", async () => {
      const res = await fetch(`${BACKEND_URL}/api/settings/suppression-list`, {
        headers: { Authorization: "Bearer invalid.fake.token" },
      });
      assert.strictEqual(res.status, 401, "Must reject invalid Bearer token");
    });

    it("rejects unauthenticated requests to /api/auth/me", async () => {
      const res = await fetch(`${BACKEND_URL}/api/auth/me`);
      assert.strictEqual(res.status, 401, "Must reject without token");
    });
  });

  // Feature 6: Frontend Route Availability & App Shell Integrity
  describe("6. Frontend Route Availability & Clean Redirection", () => {
    const routes = [
      "/login",
      "/analytics",
      "/settings",
      "/templates",
      "/campaigns",
      "/pipeline",
      "/tasks",
    ];

    for (const route of routes) {
      it(`serves ${route} with valid HTTP status (200 or 307 redirect)`, async () => {
        const res = await fetch(`${FRONTEND_URL}${route}`, { redirect: "manual" });
        // /login is 200 OK. Protected dashboard routes return 307 Redirect to /login when unauthenticated
        assert.ok(
          res.status === 200 || res.status === 307,
          `Route ${route} returned unexpected status ${res.status}`
        );
      });
    }
  });
});
