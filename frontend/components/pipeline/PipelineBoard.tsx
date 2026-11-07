"use client";

import React, { useState } from "react";
import {
  Archive,
  ChevronRight,
  Filter,
  RotateCcw,
  SlidersHorizontal,
  X,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { PipelineColumn } from "./PipelineColumn";
import { api, ApiClientError } from "@/lib/api";
import type {
  PipelineBoardResponse,
  PipelineLeadCard,
  ManualPipelineStage,
  PipelineStage,
} from "@/types";
import {
  ACTIVE_PIPELINE_COLUMNS,
  CLOSED_RAIL_COLUMNS,
  ALLOWED_MANUAL_STAGES,
} from "@/types";

interface PipelineBoardProps {
  initialData: PipelineBoardResponse;
  campaigns: Array<{ id: string; name: string }>;
  selectedCampaignId?: string;
  onCampaignChange: (campaignId: string | undefined) => void;
}

const STAGE_TITLES: Record<string, string> = {
  qualified: "Qualified",
  contacted: "Contacted",
  followup_due: "Follow-up due",
  replied: "Replied",
  interested: "Interested",
  meeting_scheduled: "Meeting scheduled",
  proposal_sent: "Proposal sent",
  negotiation: "Negotiation",
  won: "Won",
  not_interested: "Not interested",
  no_response: "No response",
  closed_lost: "Closed lost",
  opted_out: "Opted out",
};

interface UndoAction {
  leadId: string;
  leadName: string;
  previousStage: PipelineStage;
  newStage: ManualPipelineStage;
}

export function PipelineBoard({
  initialData,
  campaigns,
  selectedCampaignId,
  onCampaignChange,
}: PipelineBoardProps) {
  const [boardData, setBoardData] = useState<PipelineBoardResponse>(initialData);
  const [isClosedRailOpen, setIsClosedRailOpen] = useState(false);

  // Dialog state for optional note on 'won' or 'closed_lost'
  const [pendingNoteMove, setPendingNoteMove] = useState<{
    leadId: string;
    targetStage: ManualPipelineStage;
    leadName: string;
  } | null>(null);
  const [dealNote, setDealNote] = useState("");

  // Undo state
  const [lastUndo, setLastUndo] = useState<UndoAction | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Sync if initialData changes externally (e.g. campaign switch)
  React.useEffect(() => {
    setBoardData(initialData);
  }, [initialData]);

  // Helper to find lead in columns or closed rail
  const findLead = (leadId: string): { lead: PipelineLeadCard; sourceStage: string; isClosed: boolean } | null => {
    for (const [st, cards] of Object.entries(boardData.columns)) {
      const card = cards.find((c) => c.id === leadId);
      if (card) return { lead: card, sourceStage: st, isClosed: false };
    }
    for (const [st, cards] of Object.entries(boardData.closed)) {
      const card = cards.find((c) => c.id === leadId);
      if (card) return { lead: card, sourceStage: st, isClosed: true };
    }
    return null;
  };

  // Optimistic UI update helper
  const moveLeadInState = (
    leadId: string,
    targetStage: PipelineStage,
    notes?: string
  ): PipelineBoardResponse => {
    const nextCols: Record<string, PipelineLeadCard[]> = { ...boardData.columns };
    const nextClosed: Record<string, PipelineLeadCard[]> = { ...boardData.closed };

    let foundCard: PipelineLeadCard | null = null;

    // Remove from active columns
    for (const col of Object.keys(nextCols)) {
      const idx = nextCols[col].findIndex((c) => c.id === leadId);
      if (idx !== -1) {
        foundCard = { ...nextCols[col][idx] };
        nextCols[col] = nextCols[col].filter((c) => c.id !== leadId);
        break;
      }
    }

    // Remove from closed rail if not found yet
    if (!foundCard) {
      for (const col of Object.keys(nextClosed)) {
        const idx = nextClosed[col].findIndex((c) => c.id === leadId);
        if (idx !== -1) {
          foundCard = { ...nextClosed[col][idx] };
          nextClosed[col] = nextClosed[col].filter((c) => c.id !== leadId);
          break;
        }
      }
    }

    if (!foundCard) return boardData;

    // Update card stage and note
    foundCard.pipeline_stage = targetStage;
    if (notes !== undefined) {
      foundCard.notes = notes;
    }

    // Place into target collection
    if (ACTIVE_PIPELINE_COLUMNS.includes(targetStage)) {
      nextCols[targetStage] = [foundCard, ...(nextCols[targetStage] || [])];
    } else if (CLOSED_RAIL_COLUMNS.includes(targetStage)) {
      nextClosed[targetStage] = [foundCard, ...(nextClosed[targetStage] || [])];
    }

    // Recalculate counters
    let totalActive = 0;
    Object.values(nextCols).forEach((arr) => (totalActive += arr.length));

    return {
      ...boardData,
      columns: nextCols,
      closed: nextClosed,
      total_active_leads: totalActive,
    };
  };

  // Trigger stage transition (requests note if entering won/closed_lost)
  const handleMoveToStage = (leadId: string, targetStage: ManualPipelineStage) => {
    const leadMeta = findLead(leadId);
    if (!leadMeta) return;

    if (leadMeta.lead.pipeline_stage === targetStage) return;

    // Guard against moving opted out / suppressed leads (security & UI-UX.md §6.8)
    if (leadMeta.lead.pipeline_stage === "opted_out" || leadMeta.lead.is_suppressed) {
      setErrorMessage("Opted-out leads cannot be moved.");
      return;
    }

    // Guard against non-manual drop targets
    if (!ALLOWED_MANUAL_STAGES.includes(targetStage)) {
      setErrorMessage(`Stage '${STAGE_TITLES[targetStage] || targetStage}' cannot be moved into manually.`);
      return;
    }

    // UI-UX.md §6.8: Dropping into Won or Closed lost asks for an optional note.
    if (targetStage === "won" || targetStage === "closed_lost") {
      setDealNote(leadMeta.lead.notes || "");
      setPendingNoteMove({
        leadId,
        targetStage,
        leadName: leadMeta.lead.business_name,
      });
      return;
    }

    executeMove(leadId, targetStage);
  };

  const executeMove = async (
    leadId: string,
    targetStage: ManualPipelineStage,
    noteText?: string
  ) => {
    const leadMeta = findLead(leadId);
    if (!leadMeta) return;

    const previousStage = leadMeta.lead.pipeline_stage;
    const backupState = boardData;

    // Optimistically update board
    const nextState = moveLeadInState(leadId, targetStage, noteText);
    setBoardData(nextState);
    setErrorMessage(null);

    // Set undo action toast
    setLastUndo({
      leadId,
      leadName: leadMeta.lead.business_name,
      previousStage,
      newStage: targetStage,
    });

    try {
      await api.put(`/api/leads/${leadId}/stage`, {
        stage: targetStage,
        notes: noteText !== undefined && noteText.trim() !== "" ? noteText.trim() : undefined,
      });
    } catch (err) {
      // Revert optimistic update on failure
      setBoardData(backupState);
      const msg = err instanceof ApiClientError ? err.message : "Failed to move lead stage";
      setErrorMessage(msg);
      setLastUndo(null);
    }
  };

  const handleConfirmNoteMove = () => {
    if (!pendingNoteMove) return;
    const { leadId, targetStage } = pendingNoteMove;
    setPendingNoteMove(null);
    executeMove(leadId, targetStage, dealNote);
    setDealNote("");
  };

  const handleUndo = async () => {
    if (!lastUndo) return;
    const { leadId, previousStage } = lastUndo;
    setLastUndo(null);

    // If previous stage is a valid manual stage, revert on backend
    if (ALLOWED_MANUAL_STAGES.includes(previousStage as ManualPipelineStage)) {
      await executeMove(leadId, previousStage as ManualPipelineStage);
    } else {
      // Reverting to an automated stage is blocked by backend policy; notify cleanly
      setErrorMessage(
        `Cannot revert to '${STAGE_TITLES[previousStage] || previousStage}' because it moves only via system outreach actions.`
      );
    }
  };

  // Count closed rail leads
  const closedCount = Object.values(boardData.closed).reduce(
    (acc, cards) => acc + cards.length,
    0
  );

  const isBoardEmpty = boardData.total_active_leads === 0 && closedCount === 0;

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] min-h-[500px]">
      {/* Top Filter and Actions Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4 shrink-0">
        <div className="flex items-center gap-3">
          {/* Campaign Selector Filter */}
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <select
              value={selectedCampaignId || ""}
              onChange={(e) => onCampaignChange(e.target.value ? e.target.value : undefined)}
              className="h-8 rounded-md border border-input bg-card px-2.5 py-1 text-xs font-medium text-foreground shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              aria-label="Filter pipeline by campaign"
            >
              <option value="">All Campaigns</option>
              {campaigns.map((camp) => (
                <option key={camp.id} value={camp.id}>
                  {camp.name}
                </option>
              ))}
            </select>
          </div>

          {/* Active Leads Counter */}
          <span className="text-xs text-muted-foreground font-medium">
            <strong className="text-foreground">{boardData.total_active_leads}</strong> active leads
          </span>
        </div>

        {/* Closed Rail Drawer Toggle Button */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsClosedRailOpen(!isClosedRailOpen)}
            className={`text-xs gap-1.5 h-8 font-medium ${
              isClosedRailOpen ? "bg-muted" : ""
            }`}
          >
            <Archive className="h-3.5 w-3.5" />
            <span>Closed ({closedCount})</span>
            <ChevronRight
              className={`h-3.5 w-3.5 transition-transform duration-200 ${
                isClosedRailOpen ? "rotate-90" : ""
              }`}
            />
          </Button>
        </div>
      </div>

      {/* Error Alert Banner if an update failed */}
      {errorMessage && (
        <div className="mb-3 flex items-center justify-between rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2 text-xs text-destructive shrink-0">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-destructive/80 hover:text-destructive"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Main Kanban Columns Container */}
      {isBoardEmpty ? (
        <div className="flex-1 flex flex-col items-center justify-center rounded-xl border border-dashed border-border p-8 text-center bg-card/40">
          <SlidersHorizontal className="h-10 w-10 text-muted-foreground/60 mb-3" />
          <h3 className="font-semibold text-sm text-foreground mb-1">
            No leads in your pipeline yet.
          </h3>
          <p className="text-xs text-muted-foreground max-w-sm">
            Leads appear here once they are qualified. Run discovery or import prospect leads to begin working your pipeline.
          </p>
        </div>
      ) : (
        <div className="flex-1 overflow-x-auto overflow-y-hidden pb-2 select-none">
          <div className="flex h-full gap-3.5 min-w-max">
            {/* 9 Working Active Columns */}
            {ACTIVE_PIPELINE_COLUMNS.map((stageKey) => (
              <PipelineColumn
                key={stageKey}
                stage={stageKey}
                title={STAGE_TITLES[stageKey] || stageKey}
                leads={boardData.columns[stageKey] || []}
                onMoveToStage={handleMoveToStage}
              />
            ))}

            {/* Collapsible Closed Rail Columns */}
            {isClosedRailOpen && (
              <div className="flex gap-3.5 pl-3 border-l-2 border-dashed border-border/80">
                {CLOSED_RAIL_COLUMNS.map((stageKey) => (
                  <PipelineColumn
                    key={stageKey}
                    stage={stageKey}
                    title={STAGE_TITLES[stageKey] || stageKey}
                    leads={boardData.closed[stageKey] || []}
                    onMoveToStage={handleMoveToStage}
                    isClosedRail={true}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Undo Toast Banner */}
      {lastUndo && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-lg border border-border bg-popover px-4 py-2.5 text-xs text-popover-foreground shadow-lg animate-in fade-in slide-in-from-bottom-2">
          <span>
            Moved <strong>{lastUndo.leadName}</strong> to{" "}
            <strong>{STAGE_TITLES[lastUndo.newStage] || lastUndo.newStage}</strong>.
          </span>
          <Button
            size="sm"
            variant="ghost"
            onClick={handleUndo}
            className="h-7 px-2 text-xs font-semibold text-primary hover:bg-primary/10 gap-1"
          >
            <RotateCcw className="h-3 w-3" />
            Undo
          </Button>
          <button
            onClick={() => setLastUndo(null)}
            className="text-muted-foreground hover:text-foreground ml-1"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Optional Note Modal for Won / Closed Lost */}
      <Dialog
        open={!!pendingNoteMove}
        onOpenChange={(open) => {
          if (!open) {
            setPendingNoteMove(null);
            setDealNote("");
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold">
              Move to {pendingNoteMove ? STAGE_TITLES[pendingNoteMove.targetStage] : ""}
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Add an optional note about {pendingNoteMove?.leadName} (e.g. deal terms, reason for loss, or next steps).
            </DialogDescription>
          </DialogHeader>

          <div className="py-2 space-y-2">
            <Label htmlFor="stage-notes" className="text-xs">
              Notes (optional)
            </Label>
            <Textarea
              id="stage-notes"
              value={dealNote}
              onChange={(e) => setDealNote(e.target.value)}
              placeholder="e.g. Agreed on ₹35,000 package / Budget delayed until next quarter"
              rows={3}
              className="text-xs resize-none"
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setPendingNoteMove(null);
                setDealNote("");
              }}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={handleConfirmNoteMove}
              className="text-xs"
            >
              Confirm Move
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

