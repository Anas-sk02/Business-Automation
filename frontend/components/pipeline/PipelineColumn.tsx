"use client";

import React, { useState } from "react";
import { Lock, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { PipelineCard } from "./PipelineCard";
import type { PipelineLeadCard, ManualPipelineStage, PipelineStage } from "@/types";
import { ALLOWED_MANUAL_STAGES } from "@/types";

interface PipelineColumnProps {
  stage: PipelineStage;
  title: string;
  leads: PipelineLeadCard[];
  onMoveToStage: (leadId: string, stage: ManualPipelineStage) => void;
  isClosedRail?: boolean;
}

export function PipelineColumn({
  stage,
  title,
  leads,
  onMoveToStage,
  isClosedRail = false,
}: PipelineColumnProps) {
  const [isOver, setIsOver] = useState(false);

  // Check if this column allows manual drops
  const isAllowedManualDrop = ALLOWED_MANUAL_STAGES.includes(stage as ManualPipelineStage);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (isAllowedManualDrop) {
      e.dataTransfer.dropEffect = "move";
      setIsOver(true);
    } else {
      e.dataTransfer.dropEffect = "none";
    }
  };

  const handleDragLeave = () => {
    setIsOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsOver(false);
    if (!isAllowedManualDrop) return;

    try {
      const rawData = e.dataTransfer.getData("text/plain");
      if (!rawData) return;
      const parsed = JSON.parse(rawData);
      if (parsed.leadId && parsed.currentStage !== stage) {
        onMoveToStage(parsed.leadId, stage as ManualPipelineStage);
      }
    } catch {
      // Ignore invalid drag payload
    }
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`flex flex-col h-full rounded-xl border transition-all duration-150 min-w-[280px] max-w-[320px] w-full shrink-0 ${
        isClosedRail ? "bg-muted/60 border-border/70" : "bg-muted/30 border-border/60"
      } ${
        isOver && isAllowedManualDrop
          ? "border-primary/80 ring-2 ring-primary/20 bg-primary/5"
          : ""
      }`}
    >
      {/* Column Header */}
      <div className="flex items-center justify-between px-3.5 py-3 border-b border-border/50 bg-card/60 rounded-t-xl">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-xs tracking-tight text-foreground uppercase">
            {title}
          </span>
          <Badge
            variant="secondary"
            className="text-[11px] h-5 min-w-[20px] px-1.5 flex items-center justify-center font-semibold rounded-full"
          >
            {leads.length}
          </Badge>
        </div>

        {/* Lock / Automatic indicator for non-drop columns */}
        {!isAllowedManualDrop ? (
          <TooltipProvider delay={200}>
            <Tooltip>
              <TooltipTrigger className="text-muted-foreground/70 hover:text-foreground cursor-help p-1 rounded-sm inline-flex items-center">
                <Lock className="h-3.5 w-3.5" />
              </TooltipTrigger>
              <TooltipContent side="top" className="text-xs max-w-xs">
                Moves automatically when a message is sent.
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : (
          <span
            className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider"
            title="Manual stage — drop cards here"
          >
            Manual
          </span>
        )}
      </div>

      {/* Cards List / Drop Zone */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2.5 min-h-[160px]">
        {leads.length === 0 ? (
          <div className="flex h-32 items-center justify-center rounded-lg border border-dashed border-border/60 text-xs text-muted-foreground select-none">
            No leads here.
          </div>
        ) : (
          leads.map((lead) => (
            <PipelineCard
              key={lead.id}
              lead={lead}
              onMoveToStage={onMoveToStage}
            />
          ))
        )}
      </div>
    </div>
  );
}
