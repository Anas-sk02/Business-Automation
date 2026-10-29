"use client";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import type { EvidenceItem, SeverityLevel, VerificationStatus } from "@/types";
import {
  CheckCircle2,
  Clock,
  AlertTriangle,
  XCircle,
  ExternalLink,
} from "lucide-react";

export interface EvidenceDrawerProps {
  evidence: EvidenceItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  testedUrl?: string | null;
  screenshotUrl?: string | null;
}

export function sanitizeUrl(rawUrl: string | null | undefined): string | null {
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

export function getVerificationBadge(status: VerificationStatus): {
  label: string;
  badgeClass: string;
  icon: typeof CheckCircle2;
} {
  switch (status) {
    case "verified":
      return {
        label: "Verified by audit",
        badgeClass: "bg-good/10 text-good border-good/30",
        icon: CheckCircle2,
      };
    case "contradicted":
      return {
        label: "Contradicted by audit",
        badgeClass: "bg-problem/10 text-problem border-problem/30",
        icon: XCircle,
      };
    case "unverified":
    default:
      return {
        label: "Not verified",
        badgeClass: "bg-muted text-muted-foreground border-border",
        icon: Clock,
      };
  }
}

export function getSeverityStyle(severity: SeverityLevel): {
  label: string;
  badgeClass: string;
  borderClass: string;
} {
  switch (severity) {
    case "critical":
    case "high":
      return {
        label: severity === "critical" ? "Critical" : "High",
        badgeClass: "bg-problem/10 text-problem border-problem/30",
        borderClass: "border-l-problem",
      };
    case "medium":
      return {
        label: "Medium",
        badgeClass: "bg-caution/10 text-caution border-caution/30",
        borderClass: "border-l-caution",
      };
    case "low":
      return {
        label: "Low",
        badgeClass: "bg-muted text-muted-foreground border-border",
        borderClass: "border-l-muted-foreground/60",
      };
    case "info":
    default:
      return {
        label: "Info",
        badgeClass: "bg-muted text-muted-foreground border-border",
        borderClass: "border-l-muted-foreground/40",
      };
  }
}

export function getPossibleImpact(title: string, description: string): string {
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
  if (text.includes("alt") || text.includes("image")) {
    return "Search engines and screen-reader users may struggle to understand media content.";
  }
  if (text.includes("form") || text.includes("contact")) {
    return "Visitors looking to reach out immediately may have fewer ways to get in touch.";
  }
  return "This issue may affect site usability or search ranking depending on visitor intent.";
}

export function EvidenceDrawer({
  evidence,
  open,
  onOpenChange,
  testedUrl,
  screenshotUrl,
}: EvidenceDrawerProps) {
  if (!evidence) return null;

  const verification = getVerificationBadge(evidence.verification_status);
  const severityStyle = getSeverityStyle(evidence.severity);
  const StatusIcon = verification.icon;

  const dateObj = evidence.detected_at ? new Date(evidence.detected_at) : null;
  const formattedDate =
    dateObj && !Number.isNaN(dateObj.getTime())
      ? dateObj.toLocaleString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
      : "Timestamp not available";

  const impactNote = getPossibleImpact(evidence.finding_title, evidence.description);
  const safeTestedUrl = sanitizeUrl(testedUrl);
  const safeScreenshotUrl = sanitizeUrl(screenshotUrl);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-lg overflow-y-auto p-6 space-y-6"
      >
        <SheetHeader className="space-y-1 text-left">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            {/* Severity Pill */}
            <span
              className={`rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wider border ${severityStyle.badgeClass}`}
            >
              {severityStyle.label} severity
            </span>

            {/* Verification Status Pill */}
            <span
              className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium border ${verification.badgeClass}`}
            >
              <StatusIcon className="size-3.5" />
              {verification.label}
            </span>
          </div>

          <SheetTitle className="text-lg font-semibold text-foreground">
            {evidence.finding_title}
          </SheetTitle>
          <SheetDescription className="text-xs text-muted-foreground">
            Detected on {formattedDate}
          </SheetDescription>
        </SheetHeader>

        {/* Detailed Description */}
        <div className="space-y-2 rounded-md border border-border/70 bg-card p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Finding details
          </h4>
          <p className="text-sm text-foreground leading-relaxed">{evidence.description}</p>
        </div>

        {/* Possible Impact Section (worded as a possibility per UI-UX.md §5.4) */}
        <div className="space-y-2 rounded-md border border-caution/30 bg-caution/10 p-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-caution-foreground">
            <AlertTriangle className="size-4 text-caution shrink-0" />
            <span>Possible visitor impact</span>
          </div>
          <p className="text-xs text-caution-foreground/90 leading-relaxed">{impactNote}</p>
        </div>

        {/* Measured Values / Structured Evidence Data */}
        {evidence.evidence_data && Object.keys(evidence.evidence_data).length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Measured evidence data
            </h4>
            <div className="rounded-md border border-border/70 bg-muted/20 p-3 text-xs space-y-2 font-mono">
              {Object.entries(evidence.evidence_data).map(([key, val]) => (
                <div key={key} className="flex justify-between gap-4 border-b border-border/40 pb-1.5 last:border-0 last:pb-0">
                  <span className="text-muted-foreground break-all">{key}</span>
                  <span className="font-semibold text-foreground tabular-nums text-right break-all">
                    {val === null
                      ? "null"
                      : typeof val === "object"
                      ? JSON.stringify(val)
                      : String(val)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tested URL Context */}
        <div className="space-y-1.5 text-xs">
          <span className="text-muted-foreground uppercase tracking-wider font-semibold text-[11px]">
            Target URL
          </span>
          <div className="flex items-center gap-2 break-all text-foreground font-mono bg-muted/30 p-2.5 rounded border border-border">
            <span>{safeTestedUrl || testedUrl || "Not specified"}</span>
            {safeTestedUrl && (
              <a
                href={safeTestedUrl}
                target="_blank"
                rel="noreferrer noopener"
                className="text-primary hover:underline shrink-0"
              >
                <ExternalLink className="size-3.5" />
              </a>
            )}
          </div>
        </div>

        {/* Screenshot Context if Available */}
        {safeScreenshotUrl && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Visual context
            </h4>
            <div className="rounded border border-border bg-card overflow-hidden">
              <img
                src={safeScreenshotUrl}
                alt={`Screenshot for ${evidence.finding_title}`}
                className="w-full h-auto object-cover max-h-64 object-top"
                loading="lazy"
              />
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
