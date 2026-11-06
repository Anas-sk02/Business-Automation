"use client";

import React from "react";
import type { FunnelStep } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ArrowDownRight } from "lucide-react";

interface FunnelChartProps {
  funnel: FunnelStep[];
}

export function FunnelChart({ funnel }: FunnelChartProps) {
  if (!funnel || funnel.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Acquisition Funnel</CardTitle>
          <CardDescription>No funnel data available for the selected period.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const topCount = funnel[0]?.count || 0;

  return (
    <Card className="border border-border">
      <CardHeader className="pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <div>
            <CardTitle className="text-base font-semibold text-foreground">
              Acquisition Funnel
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground mt-0.5">
              Horizontal stage progression from discovered businesses to closed deals
            </CardDescription>
          </div>
          <div className="text-xs font-medium text-muted-foreground tabular-nums">
            Total Top-of-Funnel: <span className="font-semibold text-foreground">{topCount}</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Horizontal Bar Chart representation per UI-UX.md §6.11 */}
        <div className="space-y-3.5">
          {funnel.map((step, idx) => {
            // Bar width proportional to overall rate clamped between 3% (for visibility) and 100%
            const safeOverallRate = Number.isFinite(step.overall_rate) ? step.overall_rate : 0;
            const barWidth = step.count > 0 ? Math.min(Math.max(safeOverallRate, 3), 100) : 0;
            const isTop = idx === 0;
            const safeConversionRate = Number.isFinite(step.conversion_rate) ? step.conversion_rate : 0;

            return (
              <div key={step.name} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground w-24 sm:w-28 truncate">
                      {step.name}
                    </span>
                    <span className="font-semibold text-foreground tabular-nums">
                      {step.count.toLocaleString("en-IN")}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 tabular-nums text-muted-foreground">
                    {!isTop && (
                      <span className="flex items-center text-[11px] text-muted-foreground">
                        <ArrowDownRight className="w-3 h-3 mr-0.5 text-muted-foreground" />
                        {safeConversionRate}% from prev
                      </span>
                    )}
                    <span className="font-medium text-foreground text-[11px] min-w-[3.5rem] text-right">
                      {safeOverallRate}% of all
                    </span>
                  </div>
                </div>

                {/* Progress Track */}
                <div className="h-4 w-full bg-muted rounded overflow-hidden flex items-center p-0.5">
                  <div
                    className="h-full bg-primary rounded-sm transition-all duration-300"
                    style={{ width: `${barWidth}%` }}
                    role="progressbar"
                    aria-valuenow={safeOverallRate}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Accessible Text Summary Table per UI-UX.md §6.11 */}
        <div className="pt-4 border-t border-border">
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Funnel Summary Data
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-muted-foreground">
              <thead>
                <tr className="border-b border-border/60 text-foreground">
                  <th className="py-1.5 font-medium">Stage</th>
                  <th className="py-1.5 font-medium text-right">Leads</th>
                  <th className="py-1.5 font-medium text-right">Step Conversion</th>
                  <th className="py-1.5 font-medium text-right">Overall Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {funnel.map((step, idx) => (
                  <tr key={`summary-${step.name}`} className="hover:bg-muted/30">
                    <td className="py-1.5 font-medium text-foreground">{step.name}</td>
                    <td className="py-1.5 text-right tabular-nums text-foreground">{step.count.toLocaleString("en-IN")}</td>
                    <td className="py-1.5 text-right tabular-nums">
                      {idx === 0 ? "—" : `${step.conversion_rate}%`}
                    </td>
                    <td className="py-1.5 text-right tabular-nums font-medium text-foreground">
                      {step.overall_rate}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

