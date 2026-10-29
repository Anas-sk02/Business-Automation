"use client";

import type { WebsiteAudit, EvidenceItem } from "@/types";
import { LighthouseScores } from "./LighthouseScores";
import { ScreenshotViewer } from "./ScreenshotViewer";
import { FindingsList } from "./FindingsList";
import { Button } from "@/components/ui/button";
import {
  Globe,
  Play,
  RotateCw,
  AlertCircle,
  CheckCircle2,
  XCircle,
  ExternalLink,
} from "lucide-react";

export interface AuditReportProps {
  audit?: WebsiteAudit | null;
  evidence?: EvidenceItem[];
  desktopScreenshotUrl?: string | null;
  mobileScreenshotUrl?: string | null;
  websiteUrl?: string | null;
  isAuditing?: boolean;
  onStartAudit?: () => void;
  className?: string;
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

export function AuditReport({
  audit,
  evidence = [],
  desktopScreenshotUrl,
  mobileScreenshotUrl,
  websiteUrl,
  isAuditing = false,
  onStartAudit,
  className = "",
}: AuditReportProps) {
  // Case 1: Lead has no website per UI-UX.md §6.6
  if (!websiteUrl) {
    return (
      <div className={`rounded-lg border border-border bg-card p-8 text-center ${className}`}>
        <Globe className="mx-auto size-8 text-muted-foreground mb-2" />
        <h3 className="text-base font-semibold text-foreground">
          No website found for this business
        </h3>
        <p className="mt-1 text-xs text-muted-foreground max-w-md mx-auto">
          During discovery, no active website URL was listed in the Google Places profile.
          Outreach pitches can highlight the lack of an online web presence.
        </p>
        {evidence && evidence.length > 0 && (
          <div className="mt-6 text-left border-t border-border/60 pt-4">
            <FindingsList evidence={evidence} />
          </div>
        )}
      </div>
    );
  }

  // Case 2: Audit is currently running
  if (isAuditing || audit?.status === "running" || audit?.status === "pending") {
    return (
      <div className={`rounded-lg border border-primary/30 bg-primary/5 p-8 text-center space-y-3 ${className}`}>
        <RotateCw className="mx-auto size-8 text-primary animate-spin" />
        <h3 className="text-base font-semibold text-foreground">Audit in progress</h3>
        <p className="text-xs text-muted-foreground max-w-md mx-auto">
          Currently loading website in headless browser, inspecting mobile overflow,
          checking broken links, running Lighthouse, and capturing screenshots.
        </p>
      </div>
    );
  }

  // Case 3: No audit performed yet
  if (!audit) {
    return (
      <div className={`rounded-lg border border-border bg-card p-8 text-center space-y-3 ${className}`}>
        <Globe className="mx-auto size-8 text-muted-foreground" />
        <h3 className="text-base font-semibold text-foreground">No audit performed yet</h3>
        <p className="text-xs text-muted-foreground max-w-sm mx-auto">
          Run an automated audit to test page load speed, broken links, mobile responsiveness,
          and SEO optimization.
        </p>
        {onStartAudit && (
          <Button
            variant="default"
            size="sm"
            onClick={onStartAudit}
            disabled={isAuditing}
            className="mt-2"
          >
            <Play className="mr-2 size-3.5" /> Start audit
          </Button>
        )}
      </div>
    );
  }

  // Case 4: Audit failed or timed out
  if (audit.status === "failed" || audit.status === "timeout") {
    return (
      <div className={`rounded-lg border border-problem/30 bg-problem/5 p-6 space-y-4 ${className}`}>
        <div className="flex items-start gap-3">
          <AlertCircle className="size-5 text-problem shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              Audit {audit.status === "timeout" ? "timed out" : "failed"}
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              {audit.error_message ||
                "The site did not respond within 60 seconds or blocked headless inspection."}
            </p>
            <p className="mt-1 text-xs font-mono text-muted-foreground">
              Tested URL: {audit.tested_url}
            </p>
          </div>
        </div>

        {onStartAudit && (
          <Button
            variant="outline"
            size="sm"
            onClick={onStartAudit}
            disabled={isAuditing}
          >
            <RotateCw className="mr-2 size-3.5" /> Re-try audit
          </Button>
        )}
      </div>
    );
  }

  // Case 5: Completed audit
  const effectiveDesktopUrl =
    desktopScreenshotUrl || audit.screenshot_desktop_url;
  const effectiveMobileUrl =
    mobileScreenshotUrl || audit.screenshot_mobile_url;
  const safeTestedUrl = sanitizeUrl(audit.tested_url);

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Audit Core Metrics Card */}
      <div className="rounded-lg border border-border bg-card p-5 space-y-4">
        {/* Header Strip */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/50 pb-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              Website audit overview
            </h3>
            <p className="text-xs text-muted-foreground">
              Tested URL:{" "}
              {safeTestedUrl ? (
                <a
                  href={safeTestedUrl}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="font-mono text-primary hover:underline inline-flex items-center gap-1"
                >
                  {audit.tested_url} <ExternalLink className="size-3" />
                </a>
              ) : (
                <span className="font-mono text-foreground">{audit.tested_url}</span>
              )}
            </p>
          </div>
          <span className="text-xs px-2.5 py-1 rounded-md font-medium uppercase tracking-wide bg-good/10 text-good border border-good/30">
            Audit complete
          </span>
        </div>

        {/* 4 Metric Tiles */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded border border-border/60 bg-muted/20 p-3">
            <span className="text-[11px] text-muted-foreground">HTTP status</span>
            <div className="mt-1 font-semibold tabular-nums text-foreground">
              {audit.http_status_code ?? "N/A"}
            </div>
          </div>

          <div className="rounded border border-border/60 bg-muted/20 p-3">
            <span className="text-[11px] text-muted-foreground">Load time</span>
            <div className="mt-1 font-semibold tabular-nums text-foreground">
              {audit.load_time_seconds !== null && audit.load_time_seconds !== undefined
                ? `${audit.load_time_seconds}s`
                : "N/A"}
            </div>
          </div>

          <div className="rounded border border-border/60 bg-muted/20 p-3">
            <span className="text-[11px] text-muted-foreground">SSL security</span>
            <div className="mt-1 font-semibold text-foreground flex items-center gap-1.5">
              {audit.ssl_valid ? (
                <>
                  <CheckCircle2 className="size-3.5 text-good" />
                  <span>Valid SSL</span>
                </>
              ) : (
                <>
                  <XCircle className="size-3.5 text-problem" />
                  <span className="text-problem">Invalid / None</span>
                </>
              )}
            </div>
          </div>

          <div className="rounded border border-border/60 bg-muted/20 p-3">
            <span className="text-[11px] text-muted-foreground">Broken links</span>
            <div className="mt-1 font-semibold tabular-nums text-foreground">
              {audit.broken_link_count ?? 0}
            </div>
          </div>
        </div>

        {/* Mobile Overflow Banner if detected */}
        {audit.mobile_overflow && (
          <div className="rounded-md border border-problem/30 bg-problem/10 p-3 text-xs text-problem flex items-center justify-between">
            <span>
              Mobile layout overflows viewport by{" "}
              <strong className="tabular-nums font-semibold">
                {audit.mobile_overflow_pixels} px
              </strong>
              . Horizontal scroll detected on 375 px screen.
            </span>
            <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-problem/20 text-problem">
              Defect
            </span>
          </div>
        )}
      </div>

      {/* Lighthouse Scores */}
      <LighthouseScores
        performance={audit.lighthouse_performance}
        seo={audit.lighthouse_seo}
        accessibility={audit.lighthouse_accessibility}
        bestPractices={audit.lighthouse_best_practices}
      />

      {/* Screenshot Viewer (side-by-side desktop & mobile flat frames) */}
      <ScreenshotViewer
        desktopUrl={effectiveDesktopUrl}
        mobileUrl={effectiveMobileUrl}
        testedUrl={audit.tested_url}
        capturedAt={audit.completed_at || audit.created_at}
      />

      {/* Row-Based Findings List & Evidence Drawer */}
      <FindingsList
        evidence={evidence}
        testedUrl={audit.tested_url}
        desktopScreenshotUrl={effectiveDesktopUrl}
        mobileScreenshotUrl={effectiveMobileUrl}
      />
    </div>
  );
}
