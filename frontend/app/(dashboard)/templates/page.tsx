"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { MessageSquareQuote, Search, CheckCircle2, Clock, AlertCircle } from "lucide-react";

interface OutreachTemplate {
  id: string;
  name: string;
  purpose: string;
  category: "marketing" | "utility";
  status: "approved" | "waiting_approval" | "draft" | "rejected";
  rejectionReason?: string;
  lastUpdated: string;
}

const DEFAULT_TEMPLATES: OutreachTemplate[] = [
  {
    id: "tmpl_initial_pitch",
    name: "initial_outreach_pitch",
    purpose: "First contact pitch citing specific website audit evidence and estimated revenue opportunity",
    category: "marketing",
    status: "approved",
    lastUpdated: "2026-10-25T10:00:00Z",
  },
  {
    id: "tmpl_followup_1",
    name: "gentle_followup_reminder",
    purpose: "First follow-up sent 3 days after initial message referencing specific audit findings",
    category: "marketing",
    status: "approved",
    lastUpdated: "2026-10-26T14:30:00Z",
  },
  {
    id: "tmpl_followup_2",
    name: "value_add_mockup_offer",
    purpose: "Second follow-up offering a complimentary mobile-friendly mockup or audit breakdown",
    category: "marketing",
    status: "approved",
    lastUpdated: "2026-10-28T09:15:00Z",
  },
  {
    id: "tmpl_reengage",
    name: "quarterly_reengagement",
    purpose: "Reconnecting with leads after 90 days with updated performance benchmark report",
    category: "marketing",
    status: "waiting_approval",
    lastUpdated: "2026-11-02T16:00:00Z",
  },
  {
    id: "tmpl_quick_audit",
    name: "free_audit_summary",
    purpose: "Concise 3-bullet Lighthouse speed and mobile viewport scorecard",
    category: "utility",
    status: "approved",
    lastUpdated: "2026-10-30T11:20:00Z",
  },
];

function formatTemplateDate(isoDate?: string | null): string {
  if (!isoDate) return "—";
  try {
    const d = new Date(isoDate);
    if (isNaN(d.getTime())) return "—";
    const day = d.getDate();
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const month = months[d.getMonth()];
    const year = d.getFullYear();
    return `${day} ${month} ${year}`;
  } catch {
    return "—";
  }
}

function getStatusBadge(status: OutreachTemplate["status"], rejectionReason?: string) {
  switch (status) {
    case "approved":
      return (
        <Badge variant="outline" className="border-good/40 bg-good-soft text-good gap-1 text-[11px] font-medium">
          <CheckCircle2 className="w-3 h-3" />
          Approved
        </Badge>
      );
    case "waiting_approval":
      return (
        <Badge variant="outline" className="border-caution/40 bg-caution-soft text-caution gap-1 text-[11px] font-medium">
          <Clock className="w-3 h-3" />
          Waiting for approval
        </Badge>
      );
    case "rejected":
      return (
        <div className="space-y-0.5">
          <Badge variant="outline" className="border-problem/40 bg-problem-soft text-problem gap-1 text-[11px] font-medium">
            <AlertCircle className="w-3 h-3" />
            Rejected
          </Badge>
          {rejectionReason && (
            <p className="text-[10px] text-problem truncate max-w-[180px]">{rejectionReason}</p>
          )}
        </div>
      );
    default:
      return (
        <Badge variant="secondary" className="text-[11px] font-medium">
          Draft
        </Badge>
      );
  }
}

export default function TemplatesPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const templates = DEFAULT_TEMPLATES;

  const filteredTemplates = templates.filter((t) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase().trim();
    return t.name.toLowerCase().includes(q) || t.purpose.toLowerCase().includes(q);
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Templates
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          WhatsApp outbound message templates and approval status
        </p>
      </div>

      {/* Required Note per UI-UX.md §6.10 & decisions.md §10 */}
      <div className="p-4 rounded-md border border-border bg-card space-y-2">
        <div className="flex items-start gap-3">
          <MessageSquareQuote className="w-4 h-4 text-primary shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <p className="font-semibold text-foreground">
              Messages that start a conversation must use an approved template. Approval can take a few days.
            </p>
            <p className="text-muted-foreground leading-relaxed">
              When operating with WAHA (default), personalized AI drafts reference verified audit evidence and send directly without Meta template approval. When using Twilio, outbound templates starting conversations outside the 24-hour service window require Meta verification.
            </p>
          </div>
        </div>
      </div>

      {/* Main Templates Table */}
      <Card className="border border-border">
        <CardHeader className="pb-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base font-semibold text-foreground">
                Registered Templates
              </CardTitle>
              <CardDescription className="text-xs text-muted-foreground mt-0.5">
                Standard outreach templates configured for cold acquisition and automated follow-ups
              </CardDescription>
            </div>

            {/* Search */}
            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter templates..."
                className="pl-8 h-8 text-xs"
              />
            </div>
          </div>
        </CardHeader>

        <CardContent>
          <div className="border border-border rounded-md overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/50 border-b border-border">
                <tr className="text-muted-foreground font-medium">
                  <th className="py-2.5 px-4">Template Name</th>
                  <th className="py-2.5 px-4">Purpose</th>
                  <th className="py-2.5 px-4">Category</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4 text-right">Last Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60 text-foreground">
                {filteredTemplates.map((template) => (
                  <tr key={template.id} className="hover:bg-muted/20">
                    <td className="py-2.5 px-4 font-mono font-medium text-foreground">
                      {template.name}
                    </td>
                    <td className="py-2.5 px-4 text-muted-foreground max-w-sm">
                      {template.purpose}
                    </td>
                    <td className="py-2.5 px-4 capitalize text-muted-foreground">
                      {template.category}
                    </td>
                    <td className="py-2.5 px-4">
                      {getStatusBadge(template.status, template.rejectionReason)}
                    </td>
                    <td className="py-2.5 px-4 text-right tabular-nums text-muted-foreground">
                      {formatTemplateDate(template.lastUpdated)}
                    </td>
                  </tr>
                ))}
                {filteredTemplates.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-xs text-muted-foreground">
                      No templates match your search.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
