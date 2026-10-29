"use client";

import { useState } from "react";
import type { EvidenceItem } from "@/types";
import {
  getVerificationBadge,
  getSeverityStyle,
  EvidenceDrawer,
} from "./EvidenceDrawer";
import { Button } from "@/components/ui/button";
import { FileSearch } from "lucide-react";

export interface FindingsListProps {
  evidence: EvidenceItem[];
  testedUrl?: string | null;
  desktopScreenshotUrl?: string | null;
  mobileScreenshotUrl?: string | null;
  className?: string;
}

export function FindingsList({
  evidence = [],
  testedUrl,
  desktopScreenshotUrl,
  mobileScreenshotUrl,
  className = "",
}: FindingsListProps) {
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null);

  if (!evidence || evidence.length === 0) {
    return (
      <div className={`rounded-md border border-border/60 bg-muted/10 p-6 text-center ${className}`}>
        <FileSearch className="mx-auto size-7 text-muted-foreground mb-1.5" />
        <p className="text-xs font-medium text-foreground">No evidence findings reported</p>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          The website audit did not detect specific code or layout defects.
        </p>
      </div>
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Audit findings ({evidence.length})
        </h4>
        <span className="text-[11px] text-muted-foreground">Click View for measured details</span>
      </div>

      {/* Rows Container (Rows, not cards per UI-UX.md §5.4) */}
      <div className="divide-y divide-border border border-border rounded-lg bg-card overflow-hidden">
        {evidence.map((item) => {
          const verification = getVerificationBadge(item.verification_status);
          const severityStyle = getSeverityStyle(item.severity);
          const StatusIcon = verification.icon;

          const formattedDate = item.detected_at
            ? new Date(item.detected_at).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
              })
            : "Recently";

          // Select appropriate screenshot context based on finding type
          const screenshotForDrawer =
            item.finding_title.toLowerCase().includes("mobile") ||
            item.description.toLowerCase().includes("mobile")
              ? mobileScreenshotUrl || desktopScreenshotUrl
              : desktopScreenshotUrl || mobileScreenshotUrl;

          return (
            <div
              key={item.id}
              className={`flex flex-col justify-between gap-2 p-3.5 transition-colors hover:bg-muted/30 sm:flex-row sm:items-center ${severityStyle.borderClass}`}
              style={{ borderLeftWidth: "3px" }}
            >
              {/* Left Column: Title and Subline */}
              <div className="space-y-1 min-w-0 flex-1 pr-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-foreground">
                    {item.finding_title}
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    · {severityStyle.label} severity
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-xs text-muted-foreground">
                  <span>Tested {formattedDate}</span>
                  {testedUrl && (
                    <>
                      <span>·</span>
                      <span className="truncate max-w-xs font-mono">{testedUrl}</span>
                    </>
                  )}
                  {Boolean(item.evidence_data?.viewport_width) && (
                    <>
                      <span>·</span>
                      <span className="tabular-nums">
                        {String(item.evidence_data?.viewport_width)} px wide
                      </span>
                    </>
                  )}
                </div>
              </div>

              {/* Right Column: Verification Status (words + icon) and View Trigger */}
              <div className="flex items-center gap-3 shrink-0 self-start sm:self-center">
                <span
                  className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium border ${verification.badgeClass}`}
                >
                  <StatusIcon className="size-3.5" />
                  {verification.label}
                </span>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedEvidence(item)}
                  className="h-7 px-2.5 text-xs"
                >
                  View
                </Button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Side Drawer Modal */}
      <EvidenceDrawer
        evidence={selectedEvidence}
        open={Boolean(selectedEvidence)}
        onOpenChange={(open) => {
          if (!open) setSelectedEvidence(null);
        }}
        testedUrl={testedUrl}
        screenshotUrl={
          selectedEvidence?.finding_title.toLowerCase().includes("mobile")
            ? mobileScreenshotUrl || desktopScreenshotUrl
            : desktopScreenshotUrl || mobileScreenshotUrl
        }
      />
    </div>
  );
}
