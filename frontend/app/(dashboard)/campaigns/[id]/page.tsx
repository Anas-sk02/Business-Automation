"use client";

import { useEffect, useState, use, Suspense } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Campaign, ResponseEnvelope, CampaignStatus } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ArrowLeft,
  AlertCircle,
  Play,
  Pause,
  Trash2,
  MoreVertical,
  Loader2,
  RefreshCw,
  Search,
} from "lucide-react";

function getStatusBadge(status: CampaignStatus) {
  switch (status) {
    case "draft":
      return {
        label: "Draft",
        dotClass: "bg-muted-foreground",
        badgeClass: "border-border text-muted-foreground",
      };
    case "discovering":
      return {
        label: "Finding leads",
        dotClass: "bg-primary animate-pulse",
        badgeClass: "border-primary/30 text-primary bg-secondary",
      };
    case "discovery_complete":
      return {
        label: "Leads found",
        dotClass: "bg-good",
        badgeClass: "border-good/30 text-good bg-good-soft",
      };
    case "auditing":
      return {
        label: "Auditing",
        dotClass: "bg-caution animate-pulse",
        badgeClass: "border-caution/30 text-caution bg-caution-soft",
      };
    case "active":
      return {
        label: "Active",
        dotClass: "bg-good",
        badgeClass: "border-good/30 text-good bg-good-soft",
      };
    case "paused":
      return {
        label: "Paused",
        dotClass: "bg-caution",
        badgeClass: "border-caution/30 text-caution bg-caution-soft",
      };
    case "completed":
      return {
        label: "Completed",
        dotClass: "bg-primary",
        badgeClass: "border-primary/30 text-primary bg-secondary",
      };
    default:
      return {
        label: status,
        dotClass: "bg-muted-foreground",
        badgeClass: "border-border text-muted-foreground",
      };
  }
}

function CampaignDetailContent({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const resolvedParams = use(params);
  const campaignId = resolvedParams.id;

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Delete confirmation dialog state
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [confirmNameInput, setConfirmNameInput] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchCampaign = async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const response = await api.get<ResponseEnvelope<Campaign>>(
        `/api/campaigns/${campaignId}`
      );
      setCampaign(response.data);
    } catch {
      setLoadError("Failed to load campaign. Record not found or unowned.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCampaign();
  }, [campaignId]);

  const handlePauseResume = async () => {
    if (!campaign) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const isPaused = campaign.status === "paused";
      const actionEndpoint = isPaused
        ? `/api/campaigns/${campaign.id}/resume`
        : `/api/campaigns/${campaign.id}/pause`;

      const response = await api.post<ResponseEnvelope<Campaign>>(actionEndpoint);
      if (response?.data) {
        setCampaign(response.data);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update campaign state.";
      setActionError(msg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!campaign) return;
    setIsDeleting(true);
    setActionError(null);
    try {
      await api.delete(`/api/campaigns/${campaign.id}`);
      setIsDeleteDialogOpen(false);
      router.push("/campaigns");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete campaign.";
      setActionError(msg);
      setIsDeleting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-4 bg-muted rounded w-32 animate-pulse" />
        <div className="h-8 bg-muted rounded w-64 animate-pulse" />
        <div className="h-24 bg-card border border-border rounded-md animate-pulse" />
      </div>
    );
  }

  if (!campaign || loadError) {
    return (
      <div className="space-y-4">
        <Link
          href="/campaigns"
          className="inline-flex items-center text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-1 h-3.5 w-3.5" />
          Back to campaigns
        </Link>
        <div className="p-6 rounded-md bg-problem-soft border border-problem/30 text-problem space-y-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span className="font-medium text-sm">{loadError || "Campaign not found"}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchCampaign}
            className="border-problem/40 text-problem hover:bg-problem/10 text-xs"
          >
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const statusBadge = getStatusBadge(campaign.status);
  const isBudgetSet = campaign.max_budget > 0;
  const budgetRatio = isBudgetSet
    ? Math.min((campaign.spent_amount / campaign.max_budget) * 100, 100)
    : 0;

  return (
    <div className="space-y-8">
      {/* Action Error Banner if Pause/Resume/Delete fails */}
      {actionError && (
        <div className="p-3.5 rounded-md bg-problem-soft border border-problem/30 text-problem flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{actionError}</span>
          </div>
          <button
            onClick={() => setActionError(null)}
            className="text-problem font-medium hover:underline ml-2"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Header: Breadcrumbs + Title + Action Buttons */}
      <div className="space-y-2">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Link href="/campaigns" className="hover:text-foreground">
            Campaigns
          </Link>
          <span>/</span>
          <span className="text-foreground font-medium truncate max-w-[200px]">
            {campaign.name}
          </span>
        </div>

        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              {campaign.name}
            </h1>
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusBadge.badgeClass}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${statusBadge.dotClass}`} />
              {statusBadge.label}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* Pause / Resume action */}
            {campaign.status === "active" && (
              <Button
                variant="outline"
                size="sm"
                disabled={actionLoading}
                onClick={handlePauseResume}
                className="h-8 text-xs"
              >
                {actionLoading ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Pause className="mr-1.5 h-3.5 w-3.5" />
                )}
                Pause
              </Button>
            )}

            {campaign.status === "paused" && (
              <Button
                variant="outline"
                size="sm"
                disabled={actionLoading}
                onClick={handlePauseResume}
                className="h-8 text-xs text-good border-good/40 hover:bg-good-soft"
              >
                {actionLoading ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="mr-1.5 h-3.5 w-3.5" />
                )}
                Resume
              </Button>
            )}

            {/* Campaign Options Menu */}
            <DropdownMenu>
              <DropdownMenuTrigger
                className="inline-flex items-center justify-center h-8 w-8 rounded-md border border-input text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                aria-label="Campaign options"
              >
                <MoreVertical className="h-4 w-4" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-44">
                <DropdownMenuItem
                  onClick={() => setIsDeleteDialogOpen(true)}
                  className="text-xs text-problem focus:text-problem cursor-pointer flex items-center gap-2"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete campaign
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>

      {/* Progress Strip per UI-UX.md Section 6.5 */}
      <section className="p-4 rounded-md bg-card border border-border">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 divide-y md:divide-y-0 md:divide-x divide-border">
          <div className="space-y-1">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Discovery
            </span>
            <div className="text-sm font-semibold text-foreground tabular-nums">
              {campaign.total_leads_found} leads found
            </div>
            <div className="text-[11px] text-muted-foreground">
              {campaign.discovery_queries_completed} of {campaign.discovery_queries_total || "—"} queries
            </div>
          </div>

          <div className="space-y-1 pt-3 md:pt-0 md:pl-4">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Audit
            </span>
            <div className="text-sm font-semibold text-foreground tabular-nums">
              0 of {campaign.total_leads_found}
            </div>
            <div className="text-[11px] text-muted-foreground">
              Playwright & Lighthouse
            </div>
          </div>

          <div className="space-y-1 pt-3 md:pt-0 md:pl-4">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Analysis
            </span>
            <div className="text-sm font-semibold text-foreground tabular-nums">
              0 scored
            </div>
            <div className="text-[11px] text-muted-foreground">
              Rule-based fit calculation
            </div>
          </div>

          <div className="space-y-1 pt-3 md:pt-0 md:pl-4">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Drafts
            </span>
            <div className="text-sm font-semibold text-foreground tabular-nums">
              0 generated
            </div>
            <div className="text-[11px] text-muted-foreground">
              Pending human approval
            </div>
          </div>
        </div>
      </section>

      {/* Target Parameters & Cost Panel */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Campaign Info Card */}
        <div className="md:col-span-2 p-5 rounded-md bg-card border border-border space-y-3">
          <h2 className="text-sm font-semibold text-foreground">
            Campaign parameters
          </h2>
          <div className="grid grid-cols-2 gap-y-3 gap-x-4 text-xs">
            <div>
              <span className="text-muted-foreground block">Industry</span>
              <span className="font-medium text-foreground">
                {campaign.industry_label || campaign.industry}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block">Location</span>
              <span className="font-medium text-foreground">{campaign.location}</span>
            </div>
            <div>
              <span className="text-muted-foreground block">Service offered</span>
              <span className="font-medium text-foreground">{campaign.service_offered}</span>
            </div>
            <div>
              <span className="text-muted-foreground block">Target leads</span>
              <span className="font-medium text-foreground tabular-nums">
                {campaign.target_leads}
              </span>
            </div>
          </div>

          {campaign.keywords && campaign.keywords.length > 0 && (
            <div className="pt-2 border-t border-border flex flex-wrap gap-1.5 items-center">
              <span className="text-xs text-muted-foreground mr-1">Keywords:</span>
              {campaign.keywords.map((kw, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded text-[11px] bg-secondary text-foreground"
                >
                  {kw}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Cost Panel per UI-UX.md Section 6.5 */}
        <div className="p-5 rounded-md bg-card border border-border space-y-3 flex flex-col justify-between">
          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-foreground">
              Spend vs Budget
            </h2>
            <div className="flex items-baseline justify-between text-xs">
              <span className="text-lg font-semibold text-foreground tabular-nums">
                ₹{campaign.spent_amount || 0}
              </span>
              <span className="text-muted-foreground">
                {isBudgetSet ? `of ₹${campaign.max_budget} limit` : "No budget limit"}
              </span>
            </div>

            {isBudgetSet && (
              <div className="w-full bg-secondary rounded-full h-1.5 overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 ${
                    budgetRatio >= 80 ? "bg-caution" : "bg-primary"
                  }`}
                  style={{ width: `${budgetRatio}%` }}
                />
              </div>
            )}
          </div>

          <p className="text-[11px] text-muted-foreground">
            Tracks Google Places & AI token costs across discovery and analysis.
          </p>
        </div>
      </div>

      {/* Leads Table Section (Stage 1 Honest Empty State) */}
      <section className="space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-base font-semibold text-foreground">
            Leads in this campaign
          </h2>
          <div className="relative w-64">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              disabled
              placeholder="Filter leads (Stage 2)..."
              className="h-8 pl-8 text-xs bg-muted/40 cursor-not-allowed"
            />
          </div>
        </div>

        <div className="rounded-md border border-border bg-card p-12 text-center space-y-3">
          <p className="text-sm text-foreground font-medium">
            No leads discovered yet.
          </p>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            Lead discovery using Google Places Text Search is part of Stage 2. Once initiated, discovered businesses will appear here in the real-time review ledger.
          </p>
        </div>
      </section>

      {/* Delete Campaign Confirmation Dialog per UI-UX.md Section 5.9 */}
      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold text-foreground">
              Delete campaign
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground pt-1">
              This action cannot be undone. To confirm deletion of{" "}
              <strong className="text-foreground">{campaign.name}</strong>, type the campaign name below:
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 py-2">
            <Input
              value={confirmNameInput}
              onChange={(e) => setConfirmNameInput(e.target.value)}
              placeholder={campaign.name}
              className="h-9 text-xs"
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              size="sm"
              disabled={isDeleting}
              onClick={() => setIsDeleteDialogOpen(false)}
              className="h-8 text-xs"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={confirmNameInput !== campaign.name || isDeleting}
              onClick={handleDelete}
              className="h-8 text-xs"
            >
              {isDeleting ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : null}
              Delete campaign
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function CampaignDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return (
    <Suspense
      fallback={
        <div className="space-y-6">
          <div className="h-4 bg-muted rounded w-32 animate-pulse" />
          <div className="h-8 bg-muted rounded w-64 animate-pulse" />
          <div className="h-24 bg-card border border-border rounded-md animate-pulse" />
        </div>
      }
    >
      <CampaignDetailContent params={params} />
    </Suspense>
  );
}
