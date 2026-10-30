"use client";

import { ScoreLedger, ScoreLedgerProps } from "./ScoreLedger";

export interface ScoreBreakdownProps extends ScoreLedgerProps {
  title?: string;
}

/**
 * ScoreBreakdown component per docs/implementation.md Section 4.2.
 * Displays the 7-component Lead Fit Score ledger, component contributions, and plain-language reasons.
 */
export function ScoreBreakdown({
  score = 0,
  breakdown = {},
  reasons = [],
  hasPhone = true,
  className = "",
  title = "Lead Fit Score Breakdown",
}: ScoreBreakdownProps) {
  return (
    <div className={`space-y-3 ${className}`}>
      {title && (
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </h3>
      )}
      <ScoreLedger
        score={score}
        breakdown={breakdown}
        reasons={reasons}
        hasPhone={hasPhone}
      />
    </div>
  );
}

export default ScoreBreakdown;

