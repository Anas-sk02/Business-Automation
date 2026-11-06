"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type {
  Campaign,
  PaginatedEnvelope,
  CampaignStatus,
  TaskListResponse,
  TaskResponse,
  PipelineBoardResponse,
} from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, ArrowRight, AlertCircle, ExternalLink } from "lucide-react";

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

function getTaskTypeChip(taskType: string) {
  switch (taskType) {
    case "review_reply":
      return { label: "Replied", style: "border-primary/30 text-primary bg-primary/10" };
    case "approve_message":
      return { label: "Draft", style: "border-blue-500/30 text-blue-600 dark:text-blue-400 bg-blue-500/10" };
    case "callback":
      return { label: "Callback", style: "border-amber-500/30 text-amber-600 dark:text-amber-400 bg-amber-500/10" };
    case "schedule_meeting":
      return { label: "Meeting", style: "border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10" };
    default:
      return { label: "Task", style: "border-border text-muted-foreground bg-muted" };
  }
}

export default function TodayPage() {
  const router = useRouter();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [tasksData, setTasksData] = useState<TaskListResponse | null>(null);
  const [pipelineData, setPipelineData] = useState<PipelineBoardResponse | null>(null);
  const [upcomingTasks, setUpcomingTasks] = useState<TaskResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadTodayData() {
      try {
        // Parallel fetch for campaigns, tasks, and pipeline counts
        const [campRes, tasksRes, pipeRes, upcomingRes] = await Promise.allSettled([
          api.get<PaginatedEnvelope<Campaign>>("/api/campaigns"),
          api.get<{ data: TaskListResponse }>("/api/tasks"),
          api.get<{ data: PipelineBoardResponse }>("/api/pipeline"),
          api.get<{ data: TaskResponse[] }>("/api/tasks/upcoming?limit=10"),
        ]);

        if (campRes.status === "fulfilled") {
          setCampaigns(campRes.value.data || []);
        }
        if (tasksRes.status === "fulfilled") {
          setTasksData(tasksRes.value.data);
        }
        if (pipeRes.status === "fulfilled") {
          setPipelineData(pipeRes.value.data);
        }
        if (upcomingRes.status === "fulfilled") {
          setUpcomingTasks(upcomingRes.value.data || []);
        }
      } catch {
        // Handled silently with fallback empty state
      } finally {
        setIsLoading(false);
      }
    }
    loadTodayData();
  }, []);

  // Compute live 4 metrics per UI-UX.md Section 6.2
  const repliesWaitingCount = pipelineData?.stage_counts?.["replied"] || 0;
  const draftsToApproveCount =
    tasksData?.tasks?.filter(
      (t) => t.task_type === "approve_message" && t.status !== "completed"
    ).length || 0;
  const followupsDueCount = pipelineData?.stage_counts?.["followup_due"] || 0;
  const tasksOverdueCount = tasksData?.counts?.overdue || 0;

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
        <Link
          href="/pipeline"
          className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors"
        >
          <span className="font-semibold text-foreground tabular-nums">
            {repliesWaitingCount}
          </span>
          <span>replies waiting</span>
        </Link>

        <span className="text-border hidden sm:inline">|</span>

        <Link
          href="/tasks"
          className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors"
        >
          <span className="font-semibold text-foreground tabular-nums">
            {draftsToApproveCount}
          </span>
          <span>drafts to approve</span>
        </Link>

        <span className="text-border hidden sm:inline">|</span>

        <Link
          href="/pipeline"
          className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors"
        >
          <span className="font-semibold text-foreground tabular-nums">
            {followupsDueCount}
          </span>
          <span>follow-ups due</span>
        </Link>

        <span className="text-border hidden sm:inline">|</span>

        <Link
          href="/tasks"
          className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors"
        >
          <span className="font-semibold text-foreground tabular-nums">
            {tasksOverdueCount}
          </span>
          <span>tasks overdue</span>
        </Link>
      </div>

      {/* Needs Attention Section per UI-UX.md Section 6.2 */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-foreground">
            Needs your attention
          </h2>
          {upcomingTasks.length > 0 && (
            <Link
              href="/tasks"
              className="text-xs text-primary hover:underline font-medium"
            >
              View all ({upcomingTasks.length})
            </Link>
          )}
        </div>

        {isLoading ? (
          <div className="p-6 rounded-md bg-card border border-border space-y-2">
            <div className="h-4 bg-muted rounded w-1/3 animate-pulse" />
            <div className="h-4 bg-muted rounded w-1/2 animate-pulse" />
          </div>
        ) : upcomingTasks.length === 0 ? (
          <div className="p-8 rounded-md bg-card border border-border text-center space-y-2">
            <p className="text-sm text-muted-foreground">
              Nothing needs your attention right now.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border rounded-md border border-border bg-card overflow-hidden">
            {upcomingTasks.slice(0, 5).map((task) => {
              const chip = getTaskTypeChip(task.task_type);
              const isOverdue =
                task.due_date && new Date(task.due_date) < new Date();

              return (
                <div
                  key={task.id}
                  className="flex items-center justify-between p-3.5 hover:bg-muted/30 transition-colors text-xs"
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${chip.style}`}
                    >
                      {chip.label}
                    </span>

                    <div className="min-w-0 flex-1 space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-foreground truncate">
                          {task.title}
                        </span>
                        {task.lead_name && (
                          <span className="text-muted-foreground truncate">
                            • {task.lead_name}
                          </span>
                        )}
                      </div>
                      {task.description && (
                        <p className="text-muted-foreground text-[11px] line-clamp-1">
                          {task.description}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 ml-2">
                    {task.due_date && (
                      <span
                        className={`flex items-center gap-1 ${
                          isOverdue
                            ? "text-destructive font-semibold"
                            : "text-muted-foreground"
                        }`}
                      >
                        {isOverdue && <AlertCircle className="h-3 w-3" />}
                        {new Date(task.due_date).toLocaleDateString("en-IN", {
                          day: "numeric",
                          month: "short",
                        })}
                      </span>
                    )}

                    {task.lead_id ? (
                      <Link
                        href={`/leads/${task.lead_id}`}
                        className="inline-flex items-center gap-1 text-primary hover:underline font-medium"
                      >
                        <span>Open</span>
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    ) : (
                      <Link
                        href="/tasks"
                        className="text-primary hover:underline font-medium"
                      >
                        View
                      </Link>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
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
