"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Campaign, PaginatedEnvelope, CampaignStatus } from "@/types";
import { Button } from "@/components/ui/button";
import { Plus, ArrowRight } from "lucide-react";

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

export default function TodayPage() {
  const router = useRouter();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadCampaigns() {
      try {
        const res = await api.get<PaginatedEnvelope<Campaign>>("/api/campaigns");
        setCampaigns(res.data || []);
      } catch {
        // Handled silently
      } finally {
        setIsLoading(false);
      }
    }
    loadCampaigns();
  }, []);

  return (
    <div className="space-y-8">
      {/* Page Heading */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Today
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Your daily outreach and review work queue
          </p>
        </div>
        <Link href="/campaigns/new">
          <Button className="h-9">
            <Plus className="mr-1.5 h-4 w-4" />
            New campaign
          </Button>
        </Link>
      </div>

      {/* Four Work Queue Metrics in Single Line with Dividers per UI-UX.md Section 6.2 */}
      <div className="py-3 px-4 rounded-md bg-card border border-border flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <span className="font-semibold text-foreground tabular-nums">0</span>
          <span>replies waiting</span>
        </div>
        <span className="text-border hidden sm:inline">|</span>
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <span className="font-semibold text-foreground tabular-nums">0</span>
          <span>drafts to approve</span>
        </div>
        <span className="text-border hidden sm:inline">|</span>
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <span className="font-semibold text-foreground tabular-nums">0</span>
          <span>follow-ups due</span>
        </div>
        <span className="text-border hidden sm:inline">|</span>
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <span className="font-semibold text-foreground tabular-nums">0</span>
          <span>tasks overdue</span>
        </div>
      </div>

      {/* Needs Attention Section per UI-UX.md Section 6.2 */}
      <section className="space-y-3">
        <h2 className="text-base font-semibold text-foreground">
          Needs your attention
        </h2>
        <div className="p-8 rounded-md bg-card border border-border text-center space-y-2">
          <p className="text-sm text-muted-foreground">
            Nothing needs your attention right now.
          </p>
        </div>
      </section>

      {/* Campaigns Section: Recent Campaigns Table or Onboarding state */}
      <section className="space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-base font-semibold text-foreground">
            Campaigns
          </h2>
          {campaigns.length > 0 && (
            <Link
              href="/campaigns"
              className="text-xs text-primary hover:underline font-medium"
            >
              View all ({campaigns.length})
            </Link>
          )}
        </div>

        {isLoading ? (
          <div className="p-6 rounded-md bg-card border border-border space-y-2">
            <div className="h-4 bg-muted rounded w-1/3 animate-pulse" />
            <div className="h-4 bg-muted rounded w-1/2 animate-pulse" />
          </div>
        ) : campaigns.length === 0 ? (
          /* First-time Onboarding State per UI-UX.md Section 6.2 */
          <div className="p-6 rounded-md bg-card border border-border space-y-4">
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-foreground">
                Getting started
              </h3>
              <p className="text-xs text-muted-foreground max-w-2xl leading-relaxed">
                Create your first campaign to start finding local businesses, auditing their websites, and generating verified WhatsApp outreach drafts.
              </p>
            </div>

            <div className="pt-1">
              <Link href="/campaigns/new">
                <Button variant="outline" size="sm" className="text-xs h-8">
                  Create your first campaign <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          /* Small summary table per UI-UX.md Section 6.2 */
          <div className="rounded-md border border-border bg-card overflow-hidden">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border bg-muted/30 text-muted-foreground h-9">
                  <th className="px-4 py-2 font-medium">Campaign</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium text-right">Leads</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {campaigns.slice(0, 5).map((camp) => {
                  const status = getStatusBadge(camp.status);
                  return (
                    <tr
                      key={camp.id}
                      onClick={() => router.push(`/campaigns/${camp.id}`)}
                      className="h-10 hover:bg-secondary cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-2 font-medium text-foreground max-w-[200px] truncate">
                        {camp.name}
                      </td>
                      <td className="px-4 py-2 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${status.badgeClass}`}
                        >
                          <span className={`w-1 h-1 rounded-full ${status.dotClass}`} />
                          {status.label}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-foreground">
                        {camp.total_leads_found}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
