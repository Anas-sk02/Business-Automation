"use client";

import React from "react";
import type { CostBreakdown as CostBreakdownType } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Coins, Target, Trophy } from "lucide-react";

interface CostBreakdownProps {
  costs: CostBreakdownType;
}

export function formatInr(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return "—";
  }
  return `₹${amount.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatUsd(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return "—";
  }
  return `$${amount.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })}`;
}

export function formatServiceName(serviceKey: string): string {
  switch (serviceKey) {
    case "google_places":
      return "Places API (Discovery)";
    case "ai_analysis":
      return "AI Website Analysis";
    case "ai_classification":
      return "AI Reply Classification";
    case "ai_message_gen":
      return "AI Message Generator";
    case "whatsapp":
      return "WhatsApp Outreach";
    case "lighthouse":
      return "Lighthouse Web Audit";
    default:
      return serviceKey
        .split("_")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
  }
}

export function CostBreakdown({ costs }: CostBreakdownProps) {
  const services = costs.services || [];

  return (
    <Card className="border border-border">
      <CardHeader className="pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <div>
            <CardTitle className="text-base font-semibold text-foreground">
              Cost & Unit Economics
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground mt-0.5">
              Service expenditures in rupees (₹) with cost per acquired customer
            </CardDescription>
          </div>
          <div className="text-sm font-semibold text-foreground tabular-nums">
            Total Spend: <span className="text-primary">{formatInr(costs.total_spend_inr)}</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Unit Economics Highlight Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-3.5 rounded-md bg-muted/30 border border-border/60">
            <div className="flex items-center justify-between text-muted-foreground text-xs font-medium">
              <span>Total Expenditure</span>
              <Coins className="w-4 h-4 text-primary" />
            </div>
            <div className="mt-2 text-xl font-bold tracking-tight text-foreground tabular-nums">
              {formatInr(costs.total_spend_inr)}
            </div>
            <div className="text-[11px] text-muted-foreground mt-0.5 tabular-nums">
              {formatUsd(costs.total_spend_usd)} USD
            </div>
          </div>

          <div className="p-3.5 rounded-md bg-muted/30 border border-border/60">
            <div className="flex items-center justify-between text-muted-foreground text-xs font-medium">
              <span>Cost per Qualified Lead</span>
              <Target className="w-4 h-4 text-good" />
            </div>
            <div className="mt-2 text-xl font-bold tracking-tight text-foreground tabular-nums">
              {formatInr(costs.cost_per_qualified_lead_inr)}
            </div>
            <div className="text-[11px] text-muted-foreground mt-0.5">
              Across fit score ≥ 60 leads
            </div>
          </div>

          <div className="p-3.5 rounded-md bg-muted/30 border border-border/60">
            <div className="flex items-center justify-between text-muted-foreground text-xs font-medium">
              <span>Cost per Won Deal</span>
              <Trophy className="w-4 h-4 text-good" />
            </div>
            <div className="mt-2 text-xl font-bold tracking-tight text-foreground tabular-nums">
              {formatInr(costs.cost_per_won_deal_inr)}
            </div>
            <div className="text-[11px] text-muted-foreground mt-0.5">
              Closed acquisition cost
            </div>
          </div>
        </div>

        {/* Cost Table by Service per UI-UX.md §6.11 */}
        <div className="border border-border rounded-md overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/50 border-b border-border">
              <tr className="text-muted-foreground font-medium">
                <th className="py-2.5 px-4">Service</th>
                <th className="py-2.5 px-4 text-right">API Calls / Operations</th>
                <th className="py-2.5 px-4 text-right">Spend (₹ INR)</th>
                <th className="py-2.5 px-4 text-right">Spend ($ USD)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60 text-foreground">
              {services.map((item) => (
                <tr key={item.service} className="hover:bg-muted/20">
                  <td className="py-2.5 px-4 font-medium text-foreground">
                    {formatServiceName(item.service)}
                  </td>
                  <td className="py-2.5 px-4 text-right tabular-nums text-muted-foreground">
                    {item.api_calls.toLocaleString("en-IN")}
                  </td>
                  <td className="py-2.5 px-4 text-right font-medium tabular-nums text-foreground">
                    {formatInr(item.cost_inr)}
                  </td>
                  <td className="py-2.5 px-4 text-right tabular-nums text-muted-foreground">
                    {formatUsd(item.cost_usd)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-muted/30 border-t border-border font-semibold">
              <tr>
                <td className="py-2.5 px-4 text-foreground">Total</td>
                <td className="py-2.5 px-4 text-right tabular-nums text-foreground">
                  {services.reduce((acc, curr) => acc + (curr?.api_calls || 0), 0).toLocaleString("en-IN")}
                </td>
                <td className="py-2.5 px-4 text-right tabular-nums text-primary">
                  {formatInr(costs.total_spend_inr)}
                </td>
                <td className="py-2.5 px-4 text-right tabular-nums text-foreground">
                  {formatUsd(costs.total_spend_usd)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

