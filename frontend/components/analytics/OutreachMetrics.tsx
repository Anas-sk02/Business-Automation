"use client";

import React from "react";
import type { MessagingMetrics } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Send, CheckCircle2, Eye, MessageSquare, AlertCircle, ShieldAlert } from "lucide-react";

interface OutreachMetricsProps {
  messaging: MessagingMetrics;
}

function clampRate(rate: number | undefined): number {
  if (typeof rate !== "number" || !Number.isFinite(rate)) return 0;
  return Math.min(Math.max(rate, 0), 100);
}

export function OutreachMetrics({ messaging }: OutreachMetricsProps) {
  const safeDeliveryRate = clampRate(messaging?.delivery_rate);
  const safeReadRate = clampRate(messaging?.read_rate);
  const safeReplyRate = clampRate(messaging?.reply_rate);

  const statCards = [
    {
      label: "Messages sent",
      count: messaging?.total_sent ?? 0,
      icon: Send,
      color: "text-foreground",
    },
    {
      label: "Delivered",
      count: messaging?.total_delivered ?? 0,
      icon: CheckCircle2,
      color: "text-good",
    },
    {
      label: "Read",
      count: messaging?.total_read ?? 0,
      icon: Eye,
      color: "text-primary",
    },
    {
      label: "Replied",
      count: messaging?.total_replied ?? 0,
      icon: MessageSquare,
      color: "text-good",
    },
    {
      label: "Failed",
      count: messaging?.total_failed ?? 0,
      icon: AlertCircle,
      color: (messaging?.total_failed ?? 0) > 0 ? "text-problem" : "text-muted-foreground",
    },
    {
      label: "Opted out",
      count: messaging?.total_opted_out ?? 0,
      icon: ShieldAlert,
      color: (messaging?.total_opted_out ?? 0) > 0 ? "text-caution" : "text-muted-foreground",
    },
  ];

  return (
    <Card className="border border-border">
      <CardHeader className="pb-4">
        <CardTitle className="text-base font-semibold text-foreground">
          WhatsApp Outreach Performance
        </CardTitle>
        <CardDescription className="text-xs text-muted-foreground mt-0.5">
          Delivery reliability, read receipts, and response rates across leads
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Count summary grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {statCards.map((stat) => {
            const Icon = stat.icon;
            return (
              <div
                key={stat.label}
                className="p-3 rounded-md bg-muted/30 border border-border/60 flex flex-col justify-between"
              >
                <div className="flex items-center justify-between text-muted-foreground">
                  <span className="text-[11px] font-medium">{stat.label}</span>
                  <Icon className={`w-3.5 h-3.5 ${stat.color}`} />
                </div>
                <div className="mt-2 text-xl font-semibold tracking-tight text-foreground tabular-nums">
                  {stat.count.toLocaleString("en-IN")}
                </div>
              </div>
            );
          })}
        </div>

        {/* Conversion Rate Progress Bars */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          {/* Delivery Rate */}
          <div className="p-3.5 rounded-md border border-border bg-card space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground font-medium">Delivery rate</span>
              <span className="font-semibold text-foreground tabular-nums">
                {safeDeliveryRate}%
              </span>
            </div>
            <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-good rounded-full transition-all duration-300"
                style={{ width: `${safeDeliveryRate}%` }}
              />
            </div>
            <p className="text-[11px] text-muted-foreground">
              {messaging?.total_delivered ?? 0} of {messaging?.total_sent ?? 0} messages delivered
            </p>
          </div>

          {/* Read Rate */}
          <div className="p-3.5 rounded-md border border-border bg-card space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground font-medium">Read rate</span>
              <span className="font-semibold text-foreground tabular-nums">
                {safeReadRate}%
              </span>
            </div>
            <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-300"
                style={{ width: `${safeReadRate}%` }}
              />
            </div>
            <p className="text-[11px] text-muted-foreground">
              {messaging?.total_read ?? 0} of {messaging?.total_delivered ?? 0} delivered read
            </p>
          </div>

          {/* Reply Rate */}
          <div className="p-3.5 rounded-md border border-border bg-card space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground font-medium">Reply rate</span>
              <span className="font-semibold text-foreground tabular-nums">
                {safeReplyRate}%
              </span>
            </div>
            <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-good rounded-full transition-all duration-300"
                style={{ width: `${safeReplyRate}%` }}
              />
            </div>
            <p className="text-[11px] text-muted-foreground">
              {messaging?.total_replied ?? 0} of {messaging?.total_sent ?? 0} sent leads replied
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

