"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  MoreVertical,
  ExternalLink,
  ShieldAlert,
  Calendar,
  Building,
  CheckCircle2,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import type { PipelineLeadCard, ManualPipelineStage } from "@/types";
import { ALLOWED_MANUAL_STAGES } from "@/types";

interface PipelineCardProps {
  lead: PipelineLeadCard;
  onMoveToStage: (leadId: string, stage: ManualPipelineStage) => void;
}

const STAGE_LABELS: Record<ManualPipelineStage, string> = {
  meeting_scheduled: "Meeting scheduled",
  proposal_sent: "Proposal sent",
  negotiation: "Negotiation",
  won: "Won",
  closed_lost: "Closed lost",
  not_interested: "Not interested",
};

export function PipelineCard({
  lead,
  onMoveToStage,
}: PipelineCardProps) {
  const [isDragging, setIsDragging] = useState(false);
  const isOptedOut = lead.pipeline_stage === "opted_out" || lead.is_suppressed;

  // Format activity / date
  const lastActivityDate = lead.last_contacted_at || lead.created_at;
  const formattedDate = lastActivityDate
    ? new Date(lastActivityDate).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
      })
    : null;

  // Score tone per UI-UX.md §5.2
  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800";
    if (score >= 60) return "text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800";
    if (score >= 40) return "text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800";
    return "text-muted-foreground bg-muted border-border";
  };

  const handleDragStart = (e: React.DragEvent) => {
    if (isOptedOut) {
      e.preventDefault();
      return;
    }
    setIsDragging(true);
    e.dataTransfer.setData("text/plain", JSON.stringify({ leadId: lead.id, currentStage: lead.pipeline_stage }));
    e.dataTransfer.effectAllowed = "move";
  };

  return (
    <div
      draggable={!isOptedOut}
      onDragStart={handleDragStart}
      onDragEnd={() => setIsDragging(false)}
      className={`group relative rounded-lg border bg-card p-3 shadow-xs transition-all duration-150 hover:shadow-md ${
        isDragging ? "opacity-50 ring-2 ring-primary" : ""
      } ${
        isOptedOut
          ? "cursor-not-allowed opacity-75 border-destructive/30 bg-destructive/5"
          : "cursor-grab active:cursor-grabbing hover:border-border/80"
      }`}
    >
      {/* Header: Business Name & Move-To Menu */}
      <div className="flex items-start justify-between gap-2">
        <Link
          href={`/leads/${lead.id}`}
          className="font-medium text-sm text-foreground hover:text-primary hover:underline line-clamp-1 flex items-center gap-1.5"
          title={lead.business_name}
        >
          <span>{lead.business_name}</span>
          <ExternalLink className="h-3 w-3 shrink-0 opacity-0 group-hover:opacity-60 transition-opacity" />
        </Link>

        {/* Move To Dropdown Menu (Accessible Touch/Keyboard Navigation) */}
        {!isOptedOut && (
          <DropdownMenu>
            <DropdownMenuTrigger
              className="h-6 w-6 inline-flex items-center justify-center rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted"
              title="Move to stage"
              aria-label={`Move ${lead.business_name} to stage`}
            >
              <MoreVertical className="h-3.5 w-3.5" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48 text-xs">
              <DropdownMenuGroup>
                <DropdownMenuLabel className="text-xs font-semibold">
                  Move to stage
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {ALLOWED_MANUAL_STAGES.map((targetStage) => {
                  const isCurrent = lead.pipeline_stage === targetStage;
                  return (
                    <DropdownMenuItem
                      key={targetStage}
                      disabled={isCurrent}
                      onClick={() => onMoveToStage(lead.id, targetStage)}
                      className="cursor-pointer text-xs flex items-center justify-between"
                    >
                      <span>{STAGE_LABELS[targetStage]}</span>
                      {isCurrent && <CheckCircle2 className="h-3 w-3 text-primary" />}
                    </DropdownMenuItem>
                  );
                })}
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {/* Meta Line: Category, Location, or Campaign */}
      <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground line-clamp-1">
        {lead.category && (
          <span className="truncate">{lead.category}</span>
        )}
        {lead.category && lead.address && <span>•</span>}
        {lead.address && (
          <span className="truncate">{lead.address}</span>
        )}
        {!lead.category && !lead.address && lead.campaign_name && (
          <span className="truncate flex items-center gap-1">
            <Building className="h-3 w-3" />
            {lead.campaign_name}
          </span>
        )}
      </div>

      {/* Footer: Fit Score & Last Activity Date */}
      <div className="mt-2.5 flex items-center justify-between border-t border-border/40 pt-2 text-xs">
        <div className="flex items-center gap-1.5">
          <Badge
            variant="outline"
            className={`text-[10px] font-semibold px-1.5 py-0 rounded-xs border ${getScoreColor(
              lead.fit_score
            )}`}
            title={`Fit Score: ${lead.fit_score}/100`}
          >
            {lead.fit_score}
          </Badge>

          {isOptedOut && (
            <span
              className="inline-flex items-center gap-0.5 text-[10px] text-destructive font-medium"
              title="Prospect opted out. Cannot be moved."
            >
              <ShieldAlert className="h-3 w-3" />
              Opted out
            </span>
          )}
        </div>

        {formattedDate && (
          <span
            className="text-[11px] text-muted-foreground flex items-center gap-1"
            title={`Last activity: ${formattedDate}`}
          >
            <Calendar className="h-2.5 w-2.5 opacity-70" />
            {formattedDate}
          </span>
        )}
      </div>
    </div>
  );
}

