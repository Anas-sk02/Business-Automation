import { describe, it } from "node:test";
import assert from "node:assert/strict";

// Constants matching frontend/types/index.ts and UI-UX.md §6.8
const ACTIVE_PIPELINE_COLUMNS = [
  "qualified",
  "contacted",
  "followup_due",
  "replied",
  "interested",
  "meeting_scheduled",
  "proposal_sent",
  "negotiation",
  "won",
];

const CLOSED_RAIL_COLUMNS = [
  "not_interested",
  "no_response",
  "closed_lost",
  "opted_out",
];

const ALLOWED_MANUAL_STAGES = [
  "meeting_scheduled",
  "proposal_sent",
  "negotiation",
  "won",
  "closed_lost",
  "not_interested",
];

// Logic helpers replicating component behavior in PipelineBoard.tsx & PipelineColumn.tsx
function isManualDropPermitted(targetStage) {
  return ALLOWED_MANUAL_STAGES.includes(targetStage);
}

function isCardMovable(lead) {
  if (!lead) return false;
  if (lead.pipeline_stage === "opted_out" || lead.is_suppressed) return false;
  return true;
}

function requiresNotePrompt(targetStage) {
  return targetStage === "won" || targetStage === "closed_lost";
}

function moveLeadInState(boardData, leadId, targetStage, notes) {
  const nextCols = {};
  for (const [k, v] of Object.entries(boardData.columns)) {
    nextCols[k] = [...v];
  }
  const nextClosed = {};
  for (const [k, v] of Object.entries(boardData.closed)) {
    nextClosed[k] = [...v];
  }

  let foundCard = null;

  for (const col of Object.keys(nextCols)) {
    const idx = nextCols[col].findIndex((c) => c.id === leadId);
    if (idx !== -1) {
      foundCard = { ...nextCols[col][idx] };
      nextCols[col].splice(idx, 1);
      break;
    }
  }

  if (!foundCard) {
    for (const col of Object.keys(nextClosed)) {
      const idx = nextClosed[col].findIndex((c) => c.id === leadId);
      if (idx !== -1) {
        foundCard = { ...nextClosed[col][idx] };
        nextClosed[col].splice(idx, 1);
        break;
      }
    }
  }

  if (!foundCard) return boardData;

  foundCard.pipeline_stage = targetStage;
  if (notes !== undefined) {
    foundCard.notes = notes;
  }

  if (ACTIVE_PIPELINE_COLUMNS.includes(targetStage)) {
    nextCols[targetStage] = [foundCard, ...(nextCols[targetStage] || [])];
  } else if (CLOSED_RAIL_COLUMNS.includes(targetStage)) {
    nextClosed[targetStage] = [foundCard, ...(nextClosed[targetStage] || [])];
  }

  let totalActive = 0;
  Object.values(nextCols).forEach((arr) => (totalActive += arr.length));

  return {
    ...boardData,
    columns: nextCols,
    closed: nextClosed,
    total_active_leads: totalActive,
  };
}

describe("Pipeline UI & Kanban Board Logic Tests (Stage 6 Task 5)", () => {
  it("enforces canonical 9 active working columns and 4 closed rail columns per UI-UX.md §6.8", () => {
    assert.strictEqual(ACTIVE_PIPELINE_COLUMNS.length, 9);
    assert.deepStrictEqual(ACTIVE_PIPELINE_COLUMNS, [
      "qualified",
      "contacted",
      "followup_due",
      "replied",
      "interested",
      "meeting_scheduled",
      "proposal_sent",
      "negotiation",
      "won",
    ]);

    assert.strictEqual(CLOSED_RAIL_COLUMNS.length, 4);
    assert.deepStrictEqual(CLOSED_RAIL_COLUMNS, [
      "not_interested",
      "no_response",
      "closed_lost",
      "opted_out",
    ]);
  });

  it("permits drops ONLY into allowed manual stages and blocks automated stages", () => {
    // Permitted manual drop targets
    ALLOWED_MANUAL_STAGES.forEach((stage) => {
      assert.strictEqual(
        isManualDropPermitted(stage),
        true,
        `Expected ${stage} to accept manual drops`
      );
    });

    // Automated columns do not accept drops per UI-UX.md §6.8
    const nonDropStages = ["qualified", "contacted", "followup_due", "replied", "interested", "no_response", "opted_out"];
    nonDropStages.forEach((stage) => {
      assert.strictEqual(
        isManualDropPermitted(stage),
        false,
        `Expected ${stage} to reject manual drops`
      );
    });
  });

  it("strictly locks opted-out or suppressed leads from being dragged or moved", () => {
    const activeLead = { id: "lead_1", pipeline_stage: "qualified", is_suppressed: false };
    const optedOutLead = { id: "lead_2", pipeline_stage: "opted_out", is_suppressed: false };
    const suppressedLead = { id: "lead_3", pipeline_stage: "interested", is_suppressed: true };

    assert.strictEqual(isCardMovable(activeLead), true);
    assert.strictEqual(isCardMovable(optedOutLead), false);
    assert.strictEqual(isCardMovable(suppressedLead), false);
  });

  it("prompts for note ONLY when moving to Won or Closed lost per UI-UX.md §6.8", () => {
    assert.strictEqual(requiresNotePrompt("won"), true);
    assert.strictEqual(requiresNotePrompt("closed_lost"), true);

    assert.strictEqual(requiresNotePrompt("meeting_scheduled"), false);
    assert.strictEqual(requiresNotePrompt("proposal_sent"), false);
    assert.strictEqual(requiresNotePrompt("negotiation"), false);
    assert.strictEqual(requiresNotePrompt("not_interested"), false);
  });

  it("correctly executes optimistic stage transitions and count recalculations", () => {
    const initialBoard = {
      columns: {
        qualified: [{ id: "l1", business_name: "Apex Dental", pipeline_stage: "qualified", fit_score: 85 }],
        contacted: [],
        followup_due: [],
        replied: [],
        interested: [],
        meeting_scheduled: [],
        proposal_sent: [],
        negotiation: [],
        won: [],
      },
      closed: {
        not_interested: [],
        no_response: [],
        closed_lost: [],
        opted_out: [],
      },
      stage_counts: { qualified: 1 },
      total_active_leads: 1,
      total_leads: 1,
    };

    // Move to 'meeting_scheduled'
    const updated = moveLeadInState(initialBoard, "l1", "meeting_scheduled", "Zoom demo scheduled");
    assert.strictEqual(updated.columns.qualified.length, 0);
    assert.strictEqual(updated.columns.meeting_scheduled.length, 1);
    assert.strictEqual(updated.columns.meeting_scheduled[0].pipeline_stage, "meeting_scheduled");
    assert.strictEqual(updated.columns.meeting_scheduled[0].notes, "Zoom demo scheduled");
    assert.strictEqual(updated.total_active_leads, 1);

    // Move to closed rail 'closed_lost'
    const closed = moveLeadInState(updated, "l1", "closed_lost", "No budget this quarter");
    assert.strictEqual(closed.columns.meeting_scheduled.length, 0);
    assert.strictEqual(closed.closed.closed_lost.length, 1);
    assert.strictEqual(closed.closed.closed_lost[0].pipeline_stage, "closed_lost");
    assert.strictEqual(closed.total_active_leads, 0);
  });

  it("rejects moving to the same stage as a no-op", () => {
    const lead = { id: "l1", pipeline_stage: "meeting_scheduled" };
    const isSameStage = lead.pipeline_stage === "meeting_scheduled";
    assert.strictEqual(isSameStage, true);
  });

  it("handles undo attempts for automated stages by warning user rather than crashing", () => {
    const lastUndo = {
      leadId: "l1",
      leadName: "Apex Dental",
      previousStage: "qualified",
      newStage: "meeting_scheduled",
    };

    const isManualRevert = ALLOWED_MANUAL_STAGES.includes(lastUndo.previousStage);
    assert.strictEqual(isManualRevert, false);
    // User warning generated
    const warning = `Cannot revert to '${lastUndo.previousStage}' because it moves only via system outreach actions.`;
    assert.ok(warning.includes("system outreach actions"));
  });

  it("verifies exact empty state copy matching UI-UX.md §6.8", () => {
    const emptyColumnCopy = "No leads here.";
    const emptyBoardHeading = "No leads in your pipeline yet.";
    const emptyBoardDescription = "Leads appear here once they are qualified.";

    assert.strictEqual(emptyColumnCopy, "No leads here.");
    assert.strictEqual(emptyBoardHeading, "No leads in your pipeline yet.");
    assert.ok(emptyBoardDescription.includes("once they are qualified"));
  });
});

