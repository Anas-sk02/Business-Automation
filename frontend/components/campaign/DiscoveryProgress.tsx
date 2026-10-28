"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { api, ApiClientError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import type { DiscoveryStatus, ResponseEnvelope, CampaignStatus } from "@/types";
import { Loader2, CheckCircle2, AlertTriangle, Search, Database, Wallet } from "lucide-react";

interface DiscoveryProgressProps {
  campaignId: string;
  status: CampaignStatus;
  initialProgress?: Partial<DiscoveryStatus>;
  onStatusChange?: (newStatus: DiscoveryStatus) => void;
  onComplete?: () => void;
}

export function DiscoveryProgress({
  campaignId,
  status: initialCampaignStatus,
  initialProgress,
  onStatusChange,
  onComplete,
}: DiscoveryProgressProps) {
  const [statusData, setStatusData] = useState<DiscoveryStatus>({
    campaign_id: campaignId,
    status: initialCampaignStatus,
    discovery_queries_total: initialProgress?.discovery_queries_total || 0,
    discovery_queries_completed: initialProgress?.discovery_queries_completed || 0,
    total_leads_found: initialProgress?.total_leads_found || 0,
    target_leads: initialProgress?.target_leads || 50,
    spent_amount: initialProgress?.spent_amount || 0,
    max_budget: initialProgress?.max_budget || 0,
    is_near_budget: initialProgress?.is_near_budget || false,
    started_at: initialProgress?.started_at || null,
    completed_at: initialProgress?.completed_at || null,
  });

  const [pollError, setPollError] = useState<string | null>(null);
  const isPollingRef = useRef(false);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await api.get<ResponseEnvelope<DiscoveryStatus>>(
        `/api/campaigns/${campaignId}/status`
      );
      if (response && response.data) {
        setStatusData((prev) => {
          const updated = response.data;
          // Notify parent if status changed
          if (updated.status !== prev.status && onStatusChange) {
            onStatusChange(updated);
          }
          if (updated.status === "discovery_complete" && prev.status === "discovering" && onComplete) {
            onComplete();
          }
          return updated;
        });
        setPollError(null);
      }
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setPollError(err.message);
      } else {
        setPollError("Failed to fetch discovery status");
      }
    }
  }, [campaignId, onStatusChange, onComplete]);

  // Polling loop when discovering
  useEffect(() => {
    if (statusData.status !== "discovering") {
      isPollingRef.current = false;
      return;
    }

    isPollingRef.current = true;
    // Initial fetch immediately
    fetchStatus();

    const intervalId = setInterval(() => {
      if (isPollingRef.current) {
        fetchStatus();
      }
    }, 3000);

    return () => {
      isPollingRef.current = false;
      clearInterval(intervalId);
    };
  }, [statusData.status, fetchStatus]);

  // Percentage calculations
  const targetLeads = statusData.target_leads || 50;
  const leadsPercent = Math.min(
    Math.round((statusData.total_leads_found / targetLeads) * 100),
    100
  );

  const queriesTotal = statusData.discovery_queries_total || 1;
  const queriesCompleted = statusData.discovery_queries_completed || 0;
  const queriesPercent = Math.min(
    Math.round((queriesCompleted / queriesTotal) * 100),
    100
  );

  const isDiscovering = statusData.status === "discovering";
  const isComplete = statusData.status === "discovery_complete";

  if (!isDiscovering && !isComplete && statusData.total_leads_found === 0) {
    return null;
  }

  return (
    <Card className="border border-border/70 shadow-sm bg-card/60 backdrop-blur-sm">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            {isDiscovering ? (
              <Loader2 className="h-4 w-4 text-primary animate-spin" />
            ) : isComplete ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            ) : (
              <Search className="h-4 w-4 text-muted-foreground" />
            )}
            <CardTitle className="text-sm font-semibold text-foreground">
              {isDiscovering
                ? `Searched ${queriesCompleted} of ${queriesTotal} queries, ${statusData.total_leads_found} leads found`
                : isComplete
                ? `Discovery complete: ${statusData.total_leads_found} leads found`
                : "Discovery summary"}
            </CardTitle>
          </div>
          <Badge
            variant={isDiscovering ? "default" : isComplete ? "secondary" : "outline"}
            className="text-xs font-normal"
          >
            {isDiscovering ? "Finding leads" : isComplete ? "Leads found" : statusData.status}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Budget Warning Banner if near budget (80%+) */}
        {statusData.is_near_budget && (
          <div className="flex items-start space-x-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-500">
            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
            <div className="space-y-0.5">
              <p className="font-medium">Approaching campaign budget limit (80%+)</p>
              <p className="text-xs text-amber-500/80">
                You have spent ₹{statusData.spent_amount.toFixed(2)} of your ₹
                {statusData.max_budget.toFixed(2)} budget. Discovery will stop when the budget is reached.
              </p>
            </div>
          </div>
        )}

        {/* Polling Error Banner if any */}
        {pollError && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-xs text-destructive">
            {pollError}
          </div>
        )}

        {/* Progress Bar 1: Leads Found toward Target */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs font-medium">
            <span className="text-muted-foreground flex items-center gap-1.5">
              <Database className="h-3.5 w-3.5 text-primary" /> Leads discovered
            </span>
            <span className="text-foreground tabular-nums">
              {statusData.total_leads_found} of {statusData.target_leads} target ({leadsPercent}%)
            </span>
          </div>
          <Progress value={leadsPercent} className="h-2" />
        </div>

        {/* Progress Bar 2: Queries Completed */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs font-medium">
            <span className="text-muted-foreground flex items-center gap-1.5">
              <Search className="h-3.5 w-3.5 text-muted-foreground" /> Queries processed
            </span>
            <span className="text-muted-foreground tabular-nums">
              {queriesCompleted} of {queriesTotal} queries ({queriesPercent}%)
            </span>
          </div>
          <Progress value={queriesPercent} className="h-1.5 bg-secondary" />
        </div>

        {/* Quick Stats Grid */}
        <div className="grid grid-cols-3 gap-3 pt-1 border-t border-border/50 text-xs">
          <div>
            <span className="text-muted-foreground block text-[11px]">Total leads</span>
            <span className="font-semibold text-foreground text-sm tabular-nums">
              {statusData.total_leads_found}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block text-[11px]">Queries completed</span>
            <span className="font-semibold text-foreground text-sm tabular-nums">
              {queriesCompleted} of {queriesTotal}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block text-[11px] flex items-center gap-1">
              <Wallet className="h-3 w-3" /> API cost
            </span>
            <span className="font-semibold text-foreground text-sm tabular-nums">
              ₹{statusData.spent_amount.toFixed(2)}
              {statusData.max_budget > 0 && (
                <span className="text-muted-foreground font-normal text-[11px] tabular-nums">
                  {" "}
                  / ₹{statusData.max_budget}
                </span>
              )}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

