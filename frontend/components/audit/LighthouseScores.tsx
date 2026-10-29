"use client";

export interface LighthouseScoresProps {
  performance?: number | null;
  seo?: number | null;
  accessibility?: number | null;
  bestPractices?: number | null;
  className?: string;
}

export function getScoreThresholdTone(score: number | null | undefined): {
  tone: "problem" | "caution" | "good" | "none";
  textClass: string;
  barClass: string;
} {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return {
      tone: "none",
      textClass: "text-muted-foreground",
      barClass: "bg-muted",
    };
  }

  if (score < 50) {
    return {
      tone: "problem",
      textClass: "text-problem",
      barClass: "bg-problem",
    };
  }
  if (score < 90) {
    return {
      tone: "caution",
      textClass: "text-caution",
      barClass: "bg-caution",
    };
  }
  return {
    tone: "good",
    textClass: "text-good",
    barClass: "bg-good",
  };
}

export function LighthouseScores({
  performance,
  seo,
  accessibility,
  bestPractices,
  className = "",
}: LighthouseScoresProps) {
  const scores = [
    { label: "Performance", value: performance },
    { label: "SEO", value: seo },
    { label: "Accessibility", value: accessibility },
    { label: "Best practices", value: bestPractices },
  ];

  const hasAnyScore = scores.some(
    (s) => s.value !== null && s.value !== undefined && !Number.isNaN(s.value)
  );

  if (!hasAnyScore) {
    return (
      <div className={`rounded-md border border-border/60 bg-muted/10 p-4 ${className}`}>
        <p className="text-xs font-medium text-foreground mb-1">Lighthouse scores</p>
        <p className="text-xs text-muted-foreground">
          Performance test did not run for this site.
        </p>
      </div>
    );
  }

  return (
    <div className={`rounded-md border border-border/60 bg-muted/10 p-4 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Lighthouse scores
        </h4>
        <span className="text-[11px] text-muted-foreground">Thresholds: 0-49, 50-89, 90-100</span>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {scores.map((scoreItem) => {
          const { textClass, barClass } = getScoreThresholdTone(scoreItem.value);
          const numericValue =
            scoreItem.value !== null && scoreItem.value !== undefined
              ? Math.max(0, Math.min(100, Math.round(scoreItem.value)))
              : null;

          return (
            <div key={scoreItem.label} className="space-y-1.5">
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-muted-foreground">{scoreItem.label}</span>
                <span className={`font-semibold tabular-nums ${textClass}`}>
                  {numericValue !== null ? numericValue : "N/A"}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={`h-full transition-all duration-300 ${barClass}`}
                  style={{ width: `${numericValue ?? 0}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

