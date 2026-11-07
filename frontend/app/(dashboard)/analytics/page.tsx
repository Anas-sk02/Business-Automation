"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type {
  Campaign,
  PaginatedEnvelope,
  AnalyticsOverviewResponse,
  CampaignAnalyticsResponse,
} from "@/types";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { FunnelChart } from "@/components/analytics/FunnelChart";
import { OutreachMetrics } from "@/components/analytics/OutreachMetrics";
import { CostBreakdown, formatInr } from "@/components/analytics/CostBreakdown";
import {
  Users,
  Target,
  Send,
  Trophy,
  Coins,
  Calendar,
  AlertCircle,
  RefreshCw,
  ArrowRight,
} from "lucide-react";

type DateRangePreset = "all_time" | "last_30_days" | "last_7_days";

export default function AnalyticsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>("all");
  const [datePreset, setDatePreset] = useState<DateRangePreset>("all_time");

  const [analyticsData, setAnalyticsData] = useState<
    AnalyticsOverviewResponse | CampaignAnalyticsResponse | null
  >(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Calculate ISO date strings based on preset
  const getDateRangeParams = useCallback(() => {
    if (datePreset === "all_time") {
      return { from_date: undefined, to_date: undefined };
    }

    const now = new Date();
    const to_date = now.toISOString();
    const from = new Date(now);

    if (datePreset === "last_7_days") {
      from.setDate(now.getDate() - 7);
    } else if (datePreset === "last_30_days") {
      from.setDate(now.getDate() - 30);
    }

    return { from_date: from.toISOString(), to_date };
  }, [datePreset]);

  // Fetch campaigns for the dropdown filter
  useEffect(() => {
    async function loadCampaigns() {
      try {
        const res = await api.get<PaginatedEnvelope<Campaign>>("/api/campaigns");
        setCampaigns(Array.isArray(res?.data) ? res.data : []);
      } catch {
        // Fallback gracefully with empty campaigns list
        setCampaigns([]);
      }
    }
    loadCampaigns();
  }, []);

  // Fetch analytics metrics
  const fetchAnalytics = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    const { from_date, to_date } = getDateRangeParams();
    const queryParams = new URLSearchParams();
    if (from_date) queryParams.set("from_date", from_date);
    if (to_date) queryParams.set("to_date", to_date);

    const queryString = queryParams.toString() ? `?${queryParams.toString()}` : "";

    try {
      if (selectedCampaignId === "all") {
        const res = await api.get<{ data: AnalyticsOverviewResponse }>(
          `/api/analytics/overview${queryString}`
        );
        setAnalyticsData(res?.data ?? null);
      } else {
        const safeCampaignId = encodeURIComponent(selectedCampaignId);
        const res = await api.get<{ data: CampaignAnalyticsResponse }>(
          `/api/analytics/campaign/${safeCampaignId}${queryString}`
        );
        setAnalyticsData(res?.data ?? null);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load analytics";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [selectedCampaignId, getDateRangeParams]);

  useEffect(() => {
    let ignore = false;
    async function load() {
      const { from_date, to_date } = getDateRangeParams();
      const queryParams = new URLSearchParams();
      if (from_date) queryParams.set("from_date", from_date);
      if (to_date) queryParams.set("to_date", to_date);
      const queryString = queryParams.toString() ? `?${queryParams.toString()}` : "";

      try {
        if (selectedCampaignId === "all") {
          const res = await api.get<{ data: AnalyticsOverviewResponse }>(
            `/api/analytics/overview${queryString}`
          );
          if (!ignore) {
            setAnalyticsData(res?.data ?? null);
            setError(null);
          }
        } else {
          const safeCampaignId = encodeURIComponent(selectedCampaignId);
          const res = await api.get<{ data: CampaignAnalyticsResponse }>(
            `/api/analytics/campaign/${safeCampaignId}${queryString}`
          );
          if (!ignore) {
            setAnalyticsData(res?.data ?? null);
            setError(null);
          }
        }
      } catch (err: unknown) {
        if (!ignore) {
          const message = err instanceof Error ? err.message : "Failed to load analytics";
          setError(message);
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    load();
    return () => {
      ignore = true;
    };
  }, [selectedCampaignId, getDateRangeParams]);

  const kpis = analyticsData?.kpis;
  const hasSentMessages = analyticsData?.has_sent_messages ?? false;

  return (
    <div className="space-y-8">
      {/* Page Header and Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Analytics
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Acquisition funnel, messaging performance, and spend metrics
          </p>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Campaign Selector */}
          <select
            value={selectedCampaignId}
            onChange={(e) => setSelectedCampaignId(e.target.value)}
            className="h-9 px-3 text-xs rounded-md border border-border bg-card text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            aria-label="Filter by campaign"
          >
            <option value="all">All campaigns</option>
            {campaigns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>

          {/* Date Range Presets */}
          <div className="flex items-center rounded-md border border-border bg-card p-0.5 text-xs">
            <button
              onClick={() => setDatePreset("all_time")}
              className={`px-2.5 py-1 rounded-sm transition-colors ${
                datePreset === "all_time"
                  ? "bg-primary text-primary-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              All time
            </button>
            <button
              onClick={() => setDatePreset("last_30_days")}
              className={`px-2.5 py-1 rounded-sm transition-colors ${
                datePreset === "last_30_days"
                  ? "bg-primary text-primary-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              30 days
            </button>
            <button
              onClick={() => setDatePreset("last_7_days")}
              className={`px-2.5 py-1 rounded-sm transition-colors ${
                datePreset === "last_7_days"
                  ? "bg-primary text-primary-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              7 days
            </button>
          </div>
        </div>
      </div>

      {/* Error State */}
      {error && !isLoading && (
        <div className="p-4 rounded-md border border-problem/30 bg-problem-soft text-problem flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <Button variant="outline" size="sm" onClick={fetchAnalytics}>
            <RefreshCw className="w-3.5 h-3.5 mr-1" />
            Retry
          </Button>
        </div>
      )}

      {/* Loading Skeleton State */}
      {isLoading && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-24 w-full rounded-md" />
            ))}
          </div>
          <Skeleton className="h-80 w-full rounded-md" />
          <Skeleton className="h-64 w-full rounded-md" />
        </div>
      )}

      {/* Loaded State */}
      {!isLoading && analyticsData && (
        <>
          {/* Top KPI Cards Row */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <div className="p-3.5 rounded-md border border-border bg-card">
              <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                <span>Leads found</span>
                <Users className="w-4 h-4 text-muted-foreground" />
              </div>
              <div className="mt-2 text-2xl font-bold tracking-tight text-foreground tabular-nums">
                {kpis?.total_leads_found.toLocaleString("en-IN") || 0}
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                {kpis?.total_campaigns || 0} campaign(s)
              </div>
            </div>

            <div className="p-3.5 rounded-md border border-border bg-card">
              <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                <span>Qualified leads</span>
                <Target className="w-4 h-4 text-good" />
              </div>
              <div className="mt-2 text-2xl font-bold tracking-tight text-foreground tabular-nums">
                {kpis?.total_qualified.toLocaleString("en-IN") || 0}
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                Fit score ≥ 60
              </div>
            </div>

            <div className="p-3.5 rounded-md border border-border bg-card">
              <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                <span>Messages sent</span>
                <Send className="w-4 h-4 text-primary" />
              </div>
              <div className="mt-2 text-2xl font-bold tracking-tight text-foreground tabular-nums">
                {kpis?.total_messages_sent.toLocaleString("en-IN") || 0}
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                Outreach initiated
              </div>
            </div>

            <div className="p-3.5 rounded-md border border-border bg-card">
              <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                <span>Deals won</span>
                <Trophy className="w-4 h-4 text-good" />
              </div>
              <div className="mt-2 text-2xl font-bold tracking-tight text-foreground tabular-nums">
                {kpis?.total_deals_won.toLocaleString("en-IN") || 0}
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                Won stage clients
              </div>
            </div>

            <div className="p-3.5 rounded-md border border-border bg-card col-span-2 sm:col-span-1">
              <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                <span>Total spend</span>
                <Coins className="w-4 h-4 text-primary" />
              </div>
              <div className="mt-2 text-2xl font-bold tracking-tight text-foreground tabular-nums">
                {formatInr(kpis?.total_spend_inr || 0)}
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5 tabular-nums">
                ${(kpis?.total_spend_usd || 0).toFixed(2)} USD
              </div>
            </div>
          </div>

          {/* Empty State Banner per UI-UX.md §6.11 */}
          {!hasSentMessages ? (
            <div className="p-8 rounded-lg border border-border bg-card text-center space-y-4">
              <div className="mx-auto w-12 h-12 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
                <Calendar className="w-6 h-6 text-muted-foreground" />
              </div>
              <div className="max-w-md mx-auto space-y-1">
                <h3 className="text-base font-semibold text-foreground">
                  Analytics appear after you send your first messages.
                </h3>
                <p className="text-xs text-muted-foreground">
                  Once your WhatsApp outreach begins, conversion funnels, response metrics, and
                  customer acquisition costs will automatically populate here.
                </p>
              </div>
              <div className="pt-2">
                <Link href="/campaigns">
                  <Button size="sm" className="h-9">
                    Go to campaigns
                    <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Funnel Section */}
              <FunnelChart funnel={analyticsData.funnel} />

              {/* Messaging Metrics Section */}
              <OutreachMetrics messaging={analyticsData.messaging} />

              {/* Cost & Unit Economics Section */}
              <CostBreakdown costs={analyticsData.costs} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

