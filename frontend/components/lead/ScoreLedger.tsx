"use client";

import { AlertCircle } from "lucide-react";

export interface ScoreBreakdownItem {
  key: string;
  label: string;
  max: number;
  earned: number;
  note?: string;
}

export interface ScoreLedgerProps {
  score?: number | null;
  breakdown?: Record<string, unknown> | null;
  reasons?: string[] | null;
  hasPhone?: boolean;
  className?: string;
}

export const QUALIFY_SCORE = 60;

export function resolveEarned(
  breakdown: Record<string, unknown> | null | undefined,
  keys: string[],
  max: number
): number {
  if (!breakdown) return 0;
  for (const key of keys) {
    const raw = breakdown[key];
    const num =
      typeof raw === "number"
        ? raw
        : typeof raw === "string" && raw.trim() !== ""
        ? Number(raw)
        : NaN;
    if (!Number.isNaN(num)) {
      return Math.min(max, Math.max(0, Math.round(num)));
    }
  }
  return 0;
}

export function ScoreLedger({
  score = 0,
  breakdown = {},
  reasons = [],
  hasPhone = true,
  className = "",
}: ScoreLedgerProps) {
  const numericScore = Math.max(0, Math.min(100, Math.round(score ?? 0)));
  const qualifies = numericScore >= QUALIFY_SCORE;

  // Resolve 7 breakdown items per docs/UI-UX.md §5.3
  const items: ScoreBreakdownItem[] = [
    {
      key: "industry",
      label: "Industry fit",
      max: 20,
      earned: resolveEarned(breakdown, ["industry", "industry_fit"], 20),
    },
    {
      key: "location",
      label: "Location match",
      max: 15,
      earned: resolveEarned(breakdown, ["location", "location_match"], 15),
    },
    {
      key: "website_issues",
      label: "Website issues found",
      max: 25,
      earned: resolveEarned(
        breakdown,
        ["website", "website_issues", "website_problems"],
        25
      ),
      note: "higher score = more problems = better prospect",
    },
    {
      key: "evidence",
      label: "Evidence verified",
      max: 15,
      earned: resolveEarned(breakdown, ["evidence", "evidence_verified"], 15),
    },
    {
      key: "contact",
      label: "Contact person identified",
      max: 10,
      earned: resolveEarned(breakdown, ["contact", "contact_person"], 10),
    },
    {
      key: "phone",
      label: "Phone number verified",
      max: 10,
      earned: resolveEarned(breakdown, ["phone", "phone_verified"], 10),
    },
    {
      key: "rating",
      label: "Rating & reviews",
      max: 5,
      earned: resolveEarned(breakdown, ["rating", "rating_reviews"], 5),
    },
  ];

  const totalCalculated = items.reduce((sum, item) => sum + item.earned, 0);
  const displayTotal = totalCalculated > 0 ? totalCalculated : numericScore;

  return (
    <div className={`space-y-4 rounded-lg border border-border bg-card p-5 ${className}`}>
      {/* Header with Total Score and Status */}
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
            Fit score ledger
          </h3>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-3xl font-semibold tabular-nums text-foreground">
              {displayTotal}
            </span>
            <span className="text-sm text-muted-foreground">/ 100</span>
            <span
              className={`ml-2 text-xs font-medium px-2 py-0.5 rounded-full ${
                qualifies
                  ? "bg-primary/10 text-primary border border-primary/20"
                  : "bg-muted text-muted-foreground border border-border"
              }`}
            >
              {qualifies ? "Qualifies for outreach" : "Below qualification threshold"}
            </span>
          </div>
        </div>
        <div className="text-right text-xs text-muted-foreground">
          Qualify threshold: <span className="font-semibold tabular-nums text-foreground">60</span>
        </div>
      </div>

      {/* Progress Bar with 60% Tick */}
      <div className="space-y-1">
        <div className="relative h-3 w-full overflow-hidden rounded-full bg-muted">
          {/* Fill Bar: petrol when >= 60, muted grey when < 60 */}
          <div
            className={`h-full transition-all duration-300 ${
              qualifies ? "bg-primary" : "bg-muted-foreground/60"
            }`}
            style={{ width: `${Math.min(100, displayTotal)}%` }}
          />

          {/* Qualify line tick at 60% */}
          <div
            className="absolute top-0 bottom-0 w-[2px] bg-foreground/60 z-10"
            style={{ left: `${QUALIFY_SCORE}%` }}
            title="Qualify threshold (60)"
          />
        </div>

        {/* Marker labels */}
        <div className="relative flex justify-between text-[11px] text-muted-foreground pt-0.5">
          <span>0</span>
          <span
            className="absolute -translate-x-1/2 font-medium text-foreground"
            style={{ left: `${QUALIFY_SCORE}%` }}
          >
            Qualify (60)
          </span>
          <span>100</span>
        </div>
      </div>

      {/* Missing Phone Warning per docs/UI-UX.md §5.3 */}
      {!hasPhone && (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-md border border-caution/40 bg-caution/10 p-3 text-xs text-caution-foreground"
        >
          <AlertCircle className="size-4 shrink-0 text-caution mt-0.5" />
          <span>No phone number: WhatsApp outreach will not be possible for this lead.</span>
        </div>
      )}

      {/* 7 Breakdown Components */}
      <div className="divide-y divide-border/50 border-t border-border/50 pt-2">
        {items.map((item) => (
          <div
            key={item.key}
            className="flex items-center justify-between py-2 text-sm"
          >
            <div className="space-y-0.5">
              <span className="text-foreground">{item.label}</span>
              {item.note && (
                <p className="text-[11px] text-muted-foreground">{item.note}</p>
              )}
            </div>
            <div className="tabular-nums font-medium text-foreground">
              <span className={item.earned > 0 ? "text-foreground" : "text-muted-foreground"}>
                {item.earned}
              </span>
              <span className="text-muted-foreground text-xs font-normal"> / {item.max}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Optional Score Reasons / Signals */}
      {reasons && reasons.length > 0 && (
        <div className="border-t border-border/50 pt-3">
          <p className="text-xs font-medium text-muted-foreground mb-1.5">Score signals</p>
          <ul className="list-inside list-disc space-y-1 text-xs text-muted-foreground">
            {reasons.map((reason, idx) => (
              <li key={idx}>{reason}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
