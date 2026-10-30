"use client";

import type { AIAnalysis as AIAnalysisType } from "@/types";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  HelpCircle,
  Play,
  RotateCw,
  XCircle,
} from "lucide-react";

export interface AIAnalysisProps {
  analysis?: AIAnalysisType | null;
  isLoading?: boolean;
  isRunning?: boolean;
  onRunAnalysis?: () => void;
  className?: string;
}

export function getVerificationStatusBadge(status: string) {
  const norm = String(status || "").toLowerCase();
  switch (norm) {
    case "verified":
      return {
        label: "Verified finding",
        tone: "good",
        badgeClass: "border-good/30 text-good bg-good/10",
        icon: CheckCircle2,
      };
    case "contradicted":
      return {
        label: "Contradicted finding",
        tone: "problem",
        badgeClass: "border-problem/30 text-problem bg-problem/10",
        icon: XCircle,
      };
    case "unverified":
    default:
      return {
        label: "Unverified finding",
        tone: "neutral",
        badgeClass: "border-border text-muted-foreground bg-muted/40",
        icon: HelpCircle,
      };
  }
}

export function getConfidenceBadge(level: string) {
  const norm = String(level || "").toLowerCase();
  switch (norm) {
    case "high":
      return {
        label: "High confidence",
        badgeClass: "border-good/30 text-good bg-good/10",
      };
    case "low":
      return {
        label: "Low confidence",
        badgeClass: "border-problem/30 text-problem bg-problem/10",
      };
    case "medium":
    default:
      return {
        label: "Medium confidence",
        badgeClass: "border-caution/30 text-caution bg-caution/10",
      };
  }
}

export function AIAnalysis({
  analysis,
  isLoading = false,
  isRunning = false,
  onRunAnalysis,
  className = "",
}: AIAnalysisProps) {
  // 1. Loading Skeleton State
  if (isLoading) {
    return (
      <div className={`space-y-6 ${className}`}>
        <div className="rounded-lg border border-border bg-card p-6 space-y-4">
          <Skeleton className="h-5 w-44" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-4 w-56" />
        </div>
        <div className="rounded-lg border border-border bg-card p-6 space-y-4">
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    );
  }

  // 2. Empty State (No analysis performed yet)
  if (!analysis) {
    return (
      <div className={`rounded-lg border border-border bg-card p-8 text-center ${className}`}>
        <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-muted/60 text-muted-foreground">
          <Play className="size-6 ml-0.5" />
        </div>
        <h3 className="mt-3 text-base font-medium text-foreground">
          No AI opportunity analysis yet
        </h3>
        <p className="mt-1.5 text-xs text-muted-foreground max-w-md mx-auto leading-relaxed">
          Run analysis to extract business insights, identify verified digital opportunities from audit findings, and calculate the Lead Fit Score.
        </p>
        <div className="mt-5">
          <Button
            variant="default"
            size="sm"
            onClick={onRunAnalysis}
            disabled={isRunning}
            className="gap-2"
          >
            <RotateCw className={`size-3.5 ${isRunning ? "animate-spin" : ""}`} />
            {isRunning ? "Running analysis..." : "Run analysis"}
          </Button>
        </div>
      </div>
    );
  }

  const {
    analysis_result,
    recommended_service,
    pitch_angle,
    confidence,
    claim_verifications = [],
    model_used,
    input_tokens = 0,
    output_tokens = 0,
    api_cost_usd = 0,
  } = analysis;

  const summary = analysis_result?.business_summary || "";
  const strengths = analysis_result?.strengths || [];
  const opportunities = analysis_result?.opportunities || [];
  const recService = recommended_service || analysis_result?.recommended_service || "";
  const pitchAngle = pitch_angle || analysis_result?.pitch_angle || "";
  const confLevel = confidence || analysis_result?.confidence || "medium";
  const confBadge = getConfidenceBadge(confLevel);

  // Map opportunity verification status from claim_verifications if available
  const getOpportunityStatus = (oppTitle: string, index: number): string => {
    if (claim_verifications[index]?.status) {
      return claim_verifications[index].status;
    }
    const matched = claim_verifications.find(
      (c) => c.claim?.toLowerCase().includes(oppTitle.toLowerCase())
    );
    return matched ? matched.status : "verified";
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Low Confidence Warning Callout per docs/UI-UX.md §5.7 */}
      {String(confLevel).toLowerCase() === "low" && (
        <div className="flex items-start gap-3 rounded-lg border border-problem/30 bg-problem/10 p-4 text-xs text-foreground">
          <AlertTriangle className="size-4 shrink-0 text-problem mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold text-problem">
              Low confidence: limited evidence found
            </p>
            <p className="text-muted-foreground leading-relaxed">
              Factual audit evidence for this business is sparse. Please review the opportunities and verify findings manually before messaging.
            </p>
          </div>
        </div>
      )}

      {/* 1. Business Summary Card (Serif style + plain caption per docs/UI-UX.md §5.7) */}
      <div className="rounded-lg border border-border bg-card p-6 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Business summary
          </h3>
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${confBadge.badgeClass}`}
            >
              {confBadge.label}
            </span>
            {onRunAnalysis && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRunAnalysis}
                disabled={isRunning}
                className="h-7 text-xs gap-1.5"
              >
                <RotateCw className={`size-3 ${isRunning ? "animate-spin" : ""}`} />
                {isRunning ? "Analyzing..." : "Re-run"}
              </Button>
            )}
          </div>
        </div>

        {summary && (
          <p className="font-serif text-sm leading-relaxed text-foreground">
            {summary}
          </p>
        )}

        <p className="text-[11px] text-muted-foreground">
          Written by AI from the audit results
        </p>
      </div>

      {/* 2. Key Strengths */}
      {strengths.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-6 space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Established strengths
          </h3>
          <ul className="space-y-2">
            {strengths.map((str, idx) => (
              <li key={idx} className="flex items-start gap-2.5 text-xs text-foreground">
                <Check className="size-3.5 shrink-0 text-good mt-0.5" />
                <span>{str}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 3. Opportunities & Verified Findings */}
      <div className="rounded-lg border border-border bg-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Identified opportunities ({opportunities.length})
          </h3>
        </div>

        {opportunities.length === 0 ? (
          <p className="text-xs text-muted-foreground italic">
            No specific digital opportunities identified from available audit data.
          </p>
        ) : (
          <div className="space-y-3">
            {opportunities.map((opp, idx) => {
              const status = getOpportunityStatus(opp.issue, idx);
              const badge = getVerificationStatusBadge(status);
              const StatusIcon = badge.icon;

              return (
                <div
                  key={idx}
                  className="rounded-lg border border-border/70 bg-muted/20 p-4 space-y-2 text-xs"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h4 className="font-medium text-foreground text-sm">
                      {opp.issue}
                    </h4>
                    <span
                      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium shrink-0 ${badge.badgeClass}`}
                    >
                      <StatusIcon className="size-3" />
                      {badge.label}
                    </span>
                  </div>

                  {opp.evidence && (
                    <div className="space-y-0.5">
                      <span className="text-[11px] font-medium text-muted-foreground block">
                        Measured evidence:
                      </span>
                      <p className="text-foreground/90 font-mono text-[11px] bg-background/60 p-2 rounded border border-border/50">
                        {opp.evidence}
                      </p>
                    </div>
                  )}

                  {opp.impact && (
                    <div className="space-y-0.5">
                      <span className="text-[11px] font-medium text-muted-foreground block">
                        Potential impact:
                      </span>
                      <p className="text-muted-foreground leading-relaxed">
                        {opp.impact}
                      </p>
                    </div>
                  )}

                  {opp.recommendation && (
                    <div className="space-y-0.5 pt-1">
                      <span className="text-[11px] font-medium text-primary block">
                        Actionable recommendation:
                      </span>
                      <p className="text-foreground font-medium">
                        {opp.recommendation}
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. Recommended Service & Pitch Angle */}
      {(recService || pitchAngle) && (
        <div className="rounded-lg border border-border bg-card p-6 space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Recommended outreach angle
          </h3>

          <div className="grid gap-3 sm:grid-cols-2">
            {recService && (
              <div className="rounded border border-border/70 bg-muted/20 p-3.5 space-y-1">
                <span className="text-[11px] font-medium text-muted-foreground block">
                  Recommended service
                </span>
                <p className="text-sm font-semibold text-foreground">
                  {recService}
                </p>
              </div>
            )}

            {pitchAngle && (
              <div className="rounded border border-border/70 bg-muted/20 p-3.5 space-y-1">
                <span className="text-[11px] font-medium text-muted-foreground block">
                  Pitch angle
                </span>
                <p className="text-xs text-foreground leading-relaxed">
                  {pitchAngle}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 5. Cost & Model Tracking Metadata Footer */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4 text-[11px] text-muted-foreground">
        <span>
          Analyzed with <strong className="font-medium text-foreground">{model_used}</strong>
        </span>
        <div className="flex items-center gap-3 tabular-nums">
          <span>Tokens: {input_tokens + output_tokens} ({input_tokens} in / {output_tokens} out)</span>
          <span>•</span>
          <span>Cost: ${Number(api_cost_usd).toFixed(4)} USD</span>
        </div>
      </div>
    </div>
  );
}

export default AIAnalysis;

