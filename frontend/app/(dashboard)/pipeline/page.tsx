"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Columns3, AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PipelineBoard } from "@/components/pipeline/PipelineBoard";
import { api, ApiClientError } from "@/lib/api";
import type { PipelineBoardResponse, Campaign } from "@/types";

export default function PipelinePage() {
  const [pipelineData, setPipelineData] = useState<PipelineBoardResponse | null>(null);
  const [campaigns, setCampaigns] = useState<Array<{ id: string; name: string }>>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPipeline = useCallback(async (campaignId?: string) => {
    try {
      // 1. Fetch campaigns for filter dropdown
      const campRes = await api.get<{ data: Campaign[] }>("/api/campaigns");
      const campList = (campRes.data || []).map((c) => ({ id: c.id, name: c.name }));
      setCampaigns(campList);

      // 2. Fetch pipeline Kanban data
      const pipeRes = await api.get<{ data: PipelineBoardResponse }>(
        "/api/pipeline",
        campaignId ? { campaign_id: campaignId } : undefined
      );
      setPipelineData(pipeRes.data);
      setError(null);
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to load pipeline board";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const campRes = await api.get<{ data: Campaign[] }>("/api/campaigns");
        if (!ignore) {
          const campList = (campRes.data || []).map((c) => ({ id: c.id, name: c.name }));
          setCampaigns(campList);
        }

        const pipeRes = await api.get<{ data: PipelineBoardResponse }>(
          "/api/pipeline",
          selectedCampaignId ? { campaign_id: selectedCampaignId } : undefined
        );
        if (!ignore) {
          setPipelineData(pipeRes.data);
          setError(null);
        }
      } catch (err) {
        if (!ignore) {
          const msg = err instanceof ApiClientError ? err.message : "Failed to load pipeline board";
          setError(msg);
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }
    init();
    return () => {
      ignore = true;
    };
  }, [selectedCampaignId]);

  const handleCampaignChange = (newCampId: string | undefined) => {
    setLoading(true);
    setSelectedCampaignId(newCampId);
  };

  return (
    <div className="flex flex-col flex-1 p-6 space-y-4">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Columns3 className="h-5 w-5 text-primary" />
            Pipeline
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Active prospects progressing from qualification to closing.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setLoading(true);
            loadPipeline(selectedCampaignId);
          }}
          disabled={loading}
          className="text-xs gap-1.5 h-8 font-medium"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Loading Skeleton */}
      {loading && (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="min-w-[280px] w-[300px] h-[520px] rounded-xl border border-border/50 bg-card p-3 space-y-3 shrink-0"
            >
              <div className="flex items-center justify-between pb-2 border-b border-border/40">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-5 w-6 rounded-full" />
              </div>
              <Skeleton className="h-24 w-full rounded-lg" />
              <Skeleton className="h-24 w-full rounded-lg" />
              <Skeleton className="h-24 w-full rounded-lg" />
            </div>
          ))}
        </div>
      )}

      {/* Error Banner */}
      {!loading && error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center space-y-3">
          <div className="flex items-center justify-center text-destructive gap-2 font-medium text-sm">
            <AlertCircle className="h-5 w-5" />
            <span>{error}</span>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => loadPipeline(selectedCampaignId)}
            className="text-xs"
          >
            Try Again
          </Button>
        </div>
      )}

      {/* Pipeline Board Component */}
      {!loading && !error && pipelineData && (
        <PipelineBoard
          initialData={pipelineData}
          campaigns={campaigns}
          selectedCampaignId={selectedCampaignId}
          onCampaignChange={handleCampaignChange}
        />
      )}
    </div>
  );
}

