import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Plus, ArrowRight } from "lucide-react";

export default function TodayPage() {
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

      {/* First-time Onboarding State per UI-UX.md Section 6.2 */}
      <section className="p-6 rounded-md bg-card border border-border space-y-4">
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-foreground">
            Getting started
          </h2>
          <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
            Create your first campaign to start finding local businesses, auditing their websites, and generating verified WhatsApp outreach drafts.
          </p>
        </div>

        <div className="pt-2">
          <Link href="/campaigns/new">
            <Button variant="outline" className="text-sm">
              Create your first campaign <ArrowRight className="ml-1.5 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
