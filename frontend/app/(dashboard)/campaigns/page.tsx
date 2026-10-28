"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Campaign, PaginatedEnvelope, CampaignStatus } from "@/types";
import { Button } from "@/components/ui/button";
import { Plus, AlertCircle, RefreshCw } from "lucide-react";

/**
 * Returns human-readable label and tone styling for CampaignStatus
 * Per UI-UX.md Section 5.2 and Section 6.3
 */
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

function formatDate(dateStr?: string) {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export default function CampaignsPage() {
  const router = useRouter();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleRetry = () => {
    setIsLoading(true);
    setErrorMsg(null);
    api.get<PaginatedEnvelope<Campaign>>("/api/campaigns")
      .then((response) => {
        setCampaigns(response.data || []);
      })
      .catch(() => {
        setErrorMsg("Failed to load campaigns. Please verify backend connection.");
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    let ignore = false;
    api.get<PaginatedEnvelope<Campaign>>("/api/campaigns")
      .then((response) => {
        if (!ignore) {
          setCampaigns(response.data || []);
          setIsLoading(false);
        }
      })
      .catch(() => {
        if (!ignore) {
          setErrorMsg("Failed to load campaigns. Please verify backend connection.");
          setIsLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      {/* Header with Title and Primary New Campaign CTA */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Campaigns
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage your targeted discovery and WhatsApp outreach campaigns
          </p>
        </div>
        <Link href="/campaigns/new">
          <Button className="h-9">
            <Plus className="mr-1.5 h-4 w-4" />
            New campaign
          </Button>
        </Link>
      </div>

      {/* Error state */}
      {errorMsg && (
        <div className="p-4 rounded-md bg-problem-soft border border-problem/30 text-problem flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRetry}
            className="h-8 border-problem/40 text-problem hover:bg-problem/10"
          >
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            Retry
          </Button>
        </div>
      )}

      {/* Loading state: skeleton matching 44px rows */}
      {isLoading ? (
        <div className="rounded-md border border-border bg-card divide-y divide-border">
          <div className="h-11 bg-muted/40 px-4 flex items-center">
            <div className="h-4 bg-muted rounded w-48 animate-pulse" />
          </div>
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-11 px-4 flex items-center justify-between">
              <div className="h-4 bg-muted rounded w-1/3 animate-pulse" />
              <div className="h-4 bg-muted rounded w-20 animate-pulse" />
            </div>
          ))}
        </div>
      ) : campaigns.length === 0 ? (
        /* Honest empty state per UI-UX.md Section 6.3 */
        <div className="rounded-md border border-border bg-card p-12 text-center space-y-4">
          <div className="space-y-1">
            <h3 className="text-base font-medium text-foreground">
              No campaigns yet.
            </h3>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto">
              Create your first campaign to search local businesses, inspect opportunities, and generate tailored outreach.
            </p>
          </div>
          <Link href="/campaigns/new">
            <Button className="h-9">
              <Plus className="mr-1.5 h-4 w-4" />
              New campaign
            </Button>
          </Link>
        </div>
      ) : (
        /* Campaigns Table per UI-UX.md Section 5.5 and 6.3 */
        <div className="rounded-md border border-border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[13px] border-collapse">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-muted-foreground font-medium h-10 select-none">
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">Industry</th>
                  <th className="px-4 py-2 font-medium">Location</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium text-right">Leads</th>
                  <th className="px-4 py-2 font-medium">Last activity</th>
                  <th className="px-4 py-2 font-medium text-right">Spend / Budget</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {campaigns.map((camp) => {
                  const statusInfo = getStatusBadge(camp.status);
                  const maxBudget = camp.max_budget > 0 ? `₹${camp.max_budget}` : "No cap";
                  const spent = `₹${camp.spent_amount || 0}`;

                  return (
                    <tr
                      key={camp.id}
                      onClick={() => router.push(`/campaigns/${camp.id}`)}
                      className="h-11 hover:bg-secondary cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-2.5 font-medium text-foreground max-w-[200px] truncate">
                        {camp.name}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground max-w-[160px] truncate">
                        {camp.industry_label || camp.industry}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground max-w-[140px] truncate">
                        {camp.location}
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${statusInfo.badgeClass}`}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${statusInfo.dotClass}`} />
                          {statusInfo.label}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-foreground">
                        {camp.total_leads_found}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground whitespace-nowrap">
                        {formatDate(camp.updated_at || camp.created_at)}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-foreground whitespace-nowrap">
                        {spent} / <span className="text-muted-foreground">{maxBudget}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-2.5 border-t border-border bg-card text-xs text-muted-foreground flex justify-between items-center">
            <span>
              Showing {campaigns.length} {campaigns.length === 1 ? "campaign" : "campaigns"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
