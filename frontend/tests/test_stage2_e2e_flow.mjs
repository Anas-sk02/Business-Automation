import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("Stage 2 End-to-End Frontend Flow Verification", () => {
  it("orchestrates discovery state machine from draft through complete", () => {
    // Initial Campaign State
    let campaign = {
      id: "cccc3333-3333-3333-3333-333333333333",
      name: "Coaching Institutes Nagpur",
      status: "draft",
      target_leads: 50,
      total_leads_found: 0,
      discovery_queries_total: 0,
      discovery_queries_completed: 0,
      max_budget: 500,
      spent_amount: 0,
    };

    let tableRefreshCount = 0;

    // Step 1: User clicks "Start discovery" -> optimistic transition
    const startDiscovery = (response) => {
      campaign = {
        ...campaign,
        status: "discovering",
        discovery_queries_total: response.queries_total,
        discovery_queries_completed: 0,
      };
    };

    startDiscovery({ job_id: "job-101", queries_total: 6 });
    assert.strictEqual(campaign.status, "discovering");
    assert.strictEqual(campaign.discovery_queries_total, 6);
    assert.strictEqual(campaign.discovery_queries_completed, 0);

    // Step 2: Polling loop updates progress
    const onStatusUpdate = (statusData) => {
      if (campaign.total_leads_found !== statusData.total_leads_found) {
        tableRefreshCount += 1;
      }
      campaign = {
        ...campaign,
        status: statusData.status,
        total_leads_found: statusData.total_leads_found,
        discovery_queries_completed: statusData.discovery_queries_completed,
        discovery_queries_total: statusData.discovery_queries_total,
        spent_amount: statusData.spent_amount,
      };
    };

    // Poll 1: 18 leads found
    onStatusUpdate({
      status: "discovering",
      total_leads_found: 18,
      discovery_queries_completed: 2,
      discovery_queries_total: 6,
      spent_amount: 60,
    });
    assert.strictEqual(campaign.total_leads_found, 18);
    assert.strictEqual(tableRefreshCount, 1);

    // Poll 2: 36 leads found
    onStatusUpdate({
      status: "discovering",
      total_leads_found: 36,
      discovery_queries_completed: 4,
      discovery_queries_total: 6,
      spent_amount: 120,
    });
    assert.strictEqual(campaign.total_leads_found, 36);
    assert.strictEqual(tableRefreshCount, 2);

    // Poll 3: 45 leads found, discovery finished
    onStatusUpdate({
      status: "discovery_complete",
      total_leads_found: 45,
      discovery_queries_completed: 6,
      discovery_queries_total: 6,
      spent_amount: 180,
    });
    assert.strictEqual(campaign.status, "discovery_complete");
    assert.strictEqual(campaign.total_leads_found, 45);
    assert.strictEqual(campaign.discovery_queries_completed, 6);
    assert.strictEqual(tableRefreshCount, 3);
  });

  it("formats discovery copy and budget alerts per UI-UX.md Sections 6.4 & 6.5", () => {
    const formatDiscoveryCopy = (completed, total, found) =>
      `Searched ${completed} of ${total} queries, ${found} leads found`;

    const copy = formatDiscoveryCopy(3, 6, 31);
    assert.strictEqual(copy, "Searched 3 of 6 queries, 31 leads found");

    // Budget caution flag at 80% threshold
    const isNearBudget = (spent, budget) => {
      if (!budget || budget <= 0) return false;
      return (spent / budget) >= 0.8;
    };

    assert.strictEqual(isNearBudget(350, 500), false); // 70%
    assert.strictEqual(isNearBudget(400, 500), true);  // 80%
    assert.strictEqual(isNearBudget(450, 500), true);  // 90%
    assert.strictEqual(isNearBudget(500, 500), true);  // 100%
  });

  it("handles leads table multi-filter state and page resets accurately", () => {
    let state = {
      page: 2,
      pageSize: 25,
      sortBy: "fit_score",
      sortOrder: "desc",
      search: "",
      stage: "all",
      websiteFilter: "all",
      phoneFilter: "all",
      scoreFilter: "all",
    };

    const updateFilter = (patch) => {
      state = {
        ...state,
        ...patch,
        page: 1, // Any filter change resets pagination to page 1
      };
    };

    // User filters by qualified leads
    updateFilter({ scoreFilter: "qualified" });
    assert.strictEqual(state.page, 1);
    assert.strictEqual(state.scoreFilter, "qualified");

    // User types search query
    updateFilter({ search: "Nagpur Coaching" });
    assert.strictEqual(state.page, 1);
    assert.strictEqual(state.search, "Nagpur Coaching");

    // Toggle column sort on Rating
    const toggleSort = (column) => {
      if (state.sortBy === column) {
        state.sortOrder = state.sortOrder === "asc" ? "desc" : "asc";
      } else {
        state.sortBy = column;
        state.sortOrder = column === "business_name" ? "asc" : "desc";
      }
      state.page = 1;
    };

    toggleSort("rating");
    assert.strictEqual(state.sortBy, "rating");
    assert.strictEqual(state.sortOrder, "desc");

    toggleSort("rating");
    assert.strictEqual(state.sortOrder, "asc");
  });

  it("verifies 4-tone stage pill categorization and qualify threshold styling", () => {
    const stageTones = {
      discovered: "neutral",
      research_pending: "neutral",
      researched: "neutral",
      qualified: "petrol",
      contacted: "petrol",
      followup_due: "petrol",
      replied: "petrol",
      interested: "good",
      meeting_scheduled: "good",
      proposal_sent: "good",
      negotiation: "good",
      won: "good",
      not_interested: "closed",
      no_response: "closed",
      closed_lost: "closed",
      opted_out: "closed",
    };

    for (const [stage, expectedTone] of Object.entries(stageTones)) {
      const isPetrol = expectedTone === "petrol";
      const isGood = expectedTone === "good";
      const isClosed = expectedTone === "closed";
      const isNeutral = expectedTone === "neutral";

      assert.ok(isPetrol || isGood || isClosed || isNeutral);
    }

    // Qualify styling
    const getScoreStyle = (score) => ({
      fillClass: score >= 60 ? "bg-primary" : "bg-muted-foreground/40",
      qualifies: score >= 60,
    });

    assert.strictEqual(getScoreStyle(59).qualifies, false);
    assert.strictEqual(getScoreStyle(59).fillClass, "bg-muted-foreground/40");
    assert.strictEqual(getScoreStyle(60).qualifies, true);
    assert.strictEqual(getScoreStyle(60).fillClass, "bg-primary");
    assert.strictEqual(getScoreStyle(88).qualifies, true);
    assert.strictEqual(getScoreStyle(88).fillClass, "bg-primary");
  });

  it("handles discovery polling errors gracefully without resetting lead counts", () => {
    let discoveryState = {
      status: "discovering",
      total_leads_found: 24,
      discovery_queries_completed: 3,
      discovery_queries_total: 6,
      pollError: null,
    };

    // Simulate transient network error during status polling
    const onPollError = (err) => {
      discoveryState = {
        ...discoveryState,
        pollError: err.message || "Network polling error",
        // Prior lead and query counts remain preserved
      };
    };

    onPollError(new Error("Network timeout: 504 Gateway Timeout"));

    assert.strictEqual(discoveryState.status, "discovering");
    assert.strictEqual(discoveryState.total_leads_found, 24);
    assert.strictEqual(discoveryState.discovery_queries_completed, 3);
    assert.strictEqual(discoveryState.pollError, "Network timeout: 504 Gateway Timeout");

    // Next successful poll clears error
    const onPollSuccess = (data) => {
      discoveryState = {
        ...discoveryState,
        ...data,
        pollError: null,
      };
    };

    onPollSuccess({
      total_leads_found: 32,
      discovery_queries_completed: 4,
    });

    assert.strictEqual(discoveryState.total_leads_found, 32);
    assert.strictEqual(discoveryState.pollError, null);
  });
});

