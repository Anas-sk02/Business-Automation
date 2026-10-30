"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiClientError } from "@/lib/api";
import type {
  LeadDetail,
  ResponseEnvelope,
  StartAuditResponse,
  FullAuditReport,
  AIAnalysis as AIAnalysisType,
  StartAnalysisResponse,
} from "@/types";
import { ScoreLedger } from "@/components/lead/ScoreLedger";
import { AuditReport } from "@/components/audit/AuditReport";
import { AIAnalysis } from "@/components/analysis/AIAnalysis";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  AlertCircle,
  Play,
  RotateCw,
  ExternalLink,
  Phone,
  Mail,
  Globe,
  MapPin,
  Clock,
  Sparkles,
  Check,
  Smartphone,
} from "lucide-react";

export type LeadTab = "audit" | "analysis" | "whatsapp" | "tasks";

export function sanitizeUrl(rawUrl: string | null | undefined): string | null {
  if (!rawUrl) return null;
  const trimmed = rawUrl.trim();
  if (!trimmed) return null;
  try {
    const hasScheme = /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(trimmed);
    const candidate = hasScheme ? trimmed : `https://${trimmed}`;
    const parsed = new URL(candidate);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
  } catch {
    return null;
  }
  return null;
}

export function sanitizePhone(rawPhone: string | null | undefined): string {
  if (!rawPhone) return "";
  return rawPhone.replace(/[^\d+]/g, "");
}

export function getStageChipInfo(stage: string) {
  const norm = String(stage || "").toLowerCase();
  switch (norm) {
    case "discovered":
    case "research_pending":
    case "researched":
      return {
        label:
          norm === "research_pending"
            ? "Research pending"
            : norm === "discovered"
            ? "Discovered"
            : "Researched",
        tone: "neutral" as const,
        dotClass: "bg-muted-foreground",
        badgeClass: "border-border text-foreground bg-muted/40",
      };
    case "qualified":
      return {
        label: "Qualified",
        tone: "petrol" as const,
        dotClass: "bg-primary",
        badgeClass: "border-primary/40 text-primary bg-primary/10",
      };
    case "contacted":
      return {
        label: "Contacted",
        tone: "petrol" as const,
        dotClass: "bg-primary",
        badgeClass: "border-primary/40 text-primary bg-primary/10",
      };
    case "followup_due":
      return {
        label: "Follow-up due",
        tone: "petrol" as const,
        dotClass: "bg-primary",
        badgeClass: "border-primary/40 text-primary bg-primary/10",
      };
    case "replied":
      return {
        label: "Replied",
        tone: "petrol" as const,
        dotClass: "bg-primary",
        badgeClass: "border-primary/40 text-primary bg-primary/10",
      };
    case "interested":
      return {
        label: "Interested",
        tone: "good" as const,
        dotClass: "bg-good",
        badgeClass: "border-good/40 text-good bg-good/10",
      };
    case "meeting_scheduled":
      return {
        label: "Meeting scheduled",
        tone: "good" as const,
        dotClass: "bg-good",
        badgeClass: "border-good/40 text-good bg-good/10",
      };
    case "proposal_sent":
      return {
        label: "Proposal sent",
        tone: "good" as const,
        dotClass: "bg-good",
        badgeClass: "border-good/40 text-good bg-good/10",
      };
    case "negotiation":
      return {
        label: "Negotiation",
        tone: "good" as const,
        dotClass: "bg-good",
        badgeClass: "border-good/40 text-good bg-good/10",
      };
    case "won":
      return {
        label: "Won",
        tone: "good" as const,
        dotClass: "bg-good",
        badgeClass: "border-good/40 text-good bg-good/10",
        isWon: true,
      };
    case "not_interested":
      return {
        label: "Not interested",
        tone: "closed" as const,
        dotClass: "bg-muted-foreground/60",
        badgeClass: "border-border text-muted-foreground bg-muted/20",
      };
    case "no_response":
      return {
        label: "No response",
        tone: "closed" as const,
        dotClass: "bg-muted-foreground/60",
        badgeClass: "border-border text-muted-foreground bg-muted/20",
      };
    case "closed_lost":
      return {
        label: "Closed lost",
        tone: "closed" as const,
        dotClass: "bg-problem/70",
        badgeClass: "border-problem/30 text-problem/90 bg-problem/10",
      };
    case "opted_out":
      return {
        label: "Opted out",
        tone: "closed" as const,
        dotClass: "bg-problem/70",
        badgeClass: "border-problem/30 text-problem/90 bg-problem/10",
      };
    default:
      return {
        label: norm ? norm.replace(/_/g, " ") : "Unknown",
        tone: "neutral" as const,
        dotClass: "bg-muted-foreground",
        badgeClass: "border-border text-foreground bg-muted/40",
      };
  }
}

export function getRecommendedNextStep(
  stage: string,
  auditStatus?: string | null
): {
  title: string;
  action: string;
  description: string;
  buttonText?: string;
  tab?: LeadTab;
} {
  const norm = String(stage || "").toLowerCase();

  if (norm === "discovered" || norm === "research_pending") {
    if (!auditStatus || auditStatus === "pending") {
      return {
        title: "Start audit",
        action: "audit",
        description:
          "Run website audit to detect SEO issues, broken links, and mobile responsiveness bugs.",
        buttonText: "Start audit",
        tab: "audit",
      };
    }
    if (auditStatus === "running") {
      return {
        title: "Audit in progress",
        action: "audit_running",
        description:
          "Audit is currently inspecting the website and generating evidence findings.",
        buttonText: "Audit running...",
        tab: "audit",
      };
    }
    return {
      title: "Review findings",
      action: "review_audit",
      description:
        "Audit complete. Review evidence items and qualify this lead for outreach.",
      buttonText: "Review findings",
      tab: "audit",
    };
  }

  if (norm === "researched") {
    return {
      title: "Run analysis",
      action: "analysis",
      description:
        "Generate value angles and messaging hypotheses based on audit findings.",
      buttonText: "Run analysis",
      tab: "analysis",
    };
  }

  if (norm === "qualified") {
    return {
      title: "Create draft",
      action: "draft",
      description:
        "Generate personalized WhatsApp opening hook and value proposition.",
      buttonText: "Create draft",
      tab: "whatsapp",
    };
  }

  if (norm === "contacted") {
    return {
      title: "Awaiting response",
      action: "wait",
      description:
        "Lead contacted. System monitors replies and schedules follow-up if quiet.",
      tab: "whatsapp",
    };
  }

  if (norm === "followup_due") {
    return {
      title: "Send follow-up",
      action: "followup",
      description:
        "Follow-up due. Send subsequent value nudge or objection handling message.",
      buttonText: "Send follow-up",
      tab: "whatsapp",
    };
  }

  if (norm === "replied" || norm === "interested") {
    return {
      title: "Schedule call",
      action: "call",
      description:
        "Lead is interested! Schedule a 15-minute discovery consultation.",
      buttonText: "Schedule call",
      tab: "tasks",
    };
  }

  if (norm === "meeting_scheduled") {
    return {
      title: "Prepare meeting",
      action: "meeting",
      description:
        "Meeting scheduled. Prepare client proposal and website audit deck.",
      buttonText: "View deck",
      tab: "tasks",
    };
  }

  if (norm === "proposal_sent" || norm === "negotiation") {
    return {
      title: "Follow up on proposal",
      action: "proposal",
      description: "Proposal delivered. Check in on contract review and terms.",
      buttonText: "Review terms",
      tab: "tasks",
    };
  }

  if (norm === "won") {
    return {
      title: "Onboard client",
      action: "won",
      description: "Deal closed! Kick off project onboarding and deliverables.",
      tab: "tasks",
    };
  }

  return {
    title: "No action required",
    action: "none",
    description:
      "Lead has been marked closed or opted out. No automated outreach will occur.",
  };
}

function LeadDetailContent({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const resolvedParams = use(params);
  const leadId = resolvedParams.id;

  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [auditReport, setAuditReport] = useState<FullAuditReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Active Tab state
  const [activeTab, setActiveTab] = useState<LeadTab>("audit");

  // Audit trigger state
  const [isAuditing, setIsAuditing] = useState(false);
  const [auditMessage, setAuditMessage] = useState<string | null>(null);
  const [auditError, setAuditError] = useState<string | null>(null);

  // AI Analysis state
  const [analysis, setAnalysis] = useState<AIAnalysisType | null>(null);
  const [isLoadingAnalysis, setIsLoadingAnalysis] = useState(false);
  const [isRunningAnalysis, setIsRunningAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const fetchAnalysis = async () => {
    try {
      setIsLoadingAnalysis(true);
      setAnalysisError(null);
      const res = await api.get<ResponseEnvelope<AIAnalysisType | null>>(
        `/api/leads/${leadId}/analysis`
      );
      setAnalysis(res.data);
    } catch {
      setAnalysis(null);
    } finally {
      setIsLoadingAnalysis(false);
    }
  };

  const fetchLead = async () => {
    try {
      setIsLoading(true);
      setLoadError(null);
      const res = await api.get<ResponseEnvelope<LeadDetail>>(`/api/leads/${leadId}`);
      setLead(res.data);

      // Attempt to load full audit report with 1-hour signed screenshot URLs
      try {
        const auditRes = await api.get<ResponseEnvelope<FullAuditReport>>(
          `/api/leads/${leadId}/audit`
        );
        setAuditReport(auditRes.data);
      } catch {
        setAuditReport(null);
      }

      // Load AI analysis
      await fetchAnalysis();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setLoadError(err.message);
      } else {
        setLoadError("Failed to load lead details. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLead();
  }, [leadId]);

  const handleStartAudit = async () => {
    try {
      setIsAuditing(true);
      setAuditError(null);
      setAuditMessage(null);

      const res = await api.post<ResponseEnvelope<StartAuditResponse>>(
        `/api/leads/${leadId}/start-audit`
      );
      setAuditMessage(res.data.message || "Audit initiated successfully.");
      // Refresh lead details to pick up newly created audit record
      await fetchLead();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setAuditError(err.message);
      } else {
        setAuditError("Failed to start website audit.");
      }
    } finally {
      setIsAuditing(false);
    }
  };

  const handleStartAnalysis = async () => {
    try {
      setIsRunningAnalysis(true);
      setAnalysisError(null);
      await api.post<ResponseEnvelope<StartAnalysisResponse>>(
        `/api/leads/${leadId}/analyze`
      );

      // Poll every 2 seconds for analysis completion (up to 10 attempts)
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts += 1;
        try {
          const res = await api.get<ResponseEnvelope<AIAnalysisType | null>>(
            `/api/leads/${leadId}/analysis`
          );
          if (res.data) {
            setAnalysis(res.data);
            clearInterval(interval);
            setIsRunningAnalysis(false);
            // Re-fetch lead so that fit_score, score_breakdown, and pipeline_stage update live
            const leadRes = await api.get<ResponseEnvelope<LeadDetail>>(`/api/leads/${leadId}`);
            setLead(leadRes.data);
          } else if (attempts >= 10) {
            clearInterval(interval);
            setIsRunningAnalysis(false);
          }
        } catch {
          if (attempts >= 10) {
            clearInterval(interval);
            setIsRunningAnalysis(false);
          }
        }
      }, 2000);
    } catch (err: unknown) {
      setIsRunningAnalysis(false);
      if (err instanceof ApiClientError) {
        setAnalysisError(err.message);
      } else {
        setAnalysisError("Failed to trigger AI analysis.");
      }
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-24" />
          <span className="text-muted-foreground">/</span>
          <Skeleton className="h-4 w-32" />
          <span className="text-muted-foreground">/</span>
          <Skeleton className="h-4 w-40" />
        </div>
        <div className="space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-96" />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
          <div className="space-y-6">
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        </div>
      </div>
    );
  }

  if (loadError || !lead) {
    return (
      <div className="rounded-lg border border-problem/30 bg-card p-8 text-center">
        <AlertCircle className="mx-auto size-10 text-problem" />
        <h2 className="mt-3 text-lg font-semibold text-foreground">Lead not found</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {loadError || "The requested lead could not be located or you lack permissions."}
        </p>
        <div className="mt-5 flex justify-center gap-3">
          <Button variant="outline" onClick={() => router.back()}>
            <ArrowLeft className="mr-2 size-4" /> Go back
          </Button>
          <Button variant="default" onClick={fetchLead}>
            <RotateCw className="mr-2 size-4" /> Try again
          </Button>
        </div>
      </div>
    );
  }

  const stageInfo = getStageChipInfo(lead.pipeline_stage);
  const auditStatus = lead.audit?.status;
  const nextStep = getRecommendedNextStep(lead.pipeline_stage, auditStatus);

  const safeWebsiteUrl = sanitizeUrl(lead.website_url);
  const safePhone = sanitizePhone(lead.phone);
  const safeEmail = lead.email ? encodeURIComponent(lead.email.trim()) : "";

  return (
    <div className="space-y-6">
      {/* Breadcrumb Navigation */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/campaigns" className="hover:text-foreground transition-colors">
          Campaigns
        </Link>
        <span>/</span>
        <Link
          href={`/campaigns/${lead.campaign_id}`}
          className="hover:text-foreground transition-colors"
        >
          Campaign leads
        </Link>
        <span>/</span>
        <span className="text-foreground font-medium truncate max-w-xs">
          {lead.business_name}
        </span>
      </nav>

      {/* Header with Business Name, Stage Chip, Sub-line and Primary Action */}
      <div className="flex flex-col gap-4 border-b border-border pb-6 md:flex-row md:items-start md:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-serif text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
              {lead.business_name}
            </h1>
            {/* Stage Chip */}
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium border ${stageInfo.badgeClass}`}
            >
              {stageInfo.isWon ? (
                <Check className="size-3 text-good stroke-[3]" />
              ) : (
                <span className={`size-1.5 rounded-full ${stageInfo.dotClass}`} />
              )}
              {stageInfo.label}
            </span>
          </div>

          {/* Sub-line: Category · City, State · Rating · Website · Phone */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            <span>{lead.category || "Not listed"}</span>
            <span>·</span>
            <span>
              {lead.city && lead.state
                ? `${lead.city}, ${lead.state}`
                : lead.city || lead.state || "Not listed"}
            </span>
            <span>·</span>
            <span className="tabular-nums">
              {lead.rating !== null && lead.rating !== undefined
                ? `${lead.rating} (${lead.review_count ?? 0} reviews)`
                : "Not listed"}
            </span>
            <span>·</span>
            {safeWebsiteUrl ? (
              <a
                href={safeWebsiteUrl}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                Website <ExternalLink className="size-3" />
              </a>
            ) : (
              <span className="text-muted-foreground">Website: Not listed</span>
            )}
            <span>·</span>
            <span>{lead.phone ? lead.phone : "Phone: Not listed"}</span>
          </div>
        </div>

        {/* Header Action Button */}
        <div className="flex items-center gap-2">
          <Button
            variant="default"
            disabled={isAuditing || auditStatus === "running"}
            onClick={handleStartAudit}
            className="shrink-0"
          >
            {isAuditing || auditStatus === "running" ? (
              <>
                <RotateCw className="mr-2 size-4 animate-spin" />
                Audit running...
              </>
            ) : lead.audit ? (
              <>
                <RotateCw className="mr-2 size-4" />
                Re-run audit
              </>
            ) : (
              <>
                <Play className="mr-2 size-4" />
                Start audit
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Audit Action Banner or Feedback */}
      {auditMessage && (
        <div className="rounded-md border border-good/40 bg-good/10 p-3 text-xs text-good">
          {auditMessage}
        </div>
      )}
      {auditError && (
        <div className="rounded-md border border-problem/40 bg-problem/10 p-3 text-xs text-problem">
          {auditError}
        </div>
      )}

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left / Main Workspace Column */}
        <div className="space-y-6 lg:col-span-2">
          {/* Score Ledger Component */}
          <ScoreLedger
            score={lead.fit_score}
            breakdown={lead.score_breakdown}
            reasons={lead.score_reasons}
            hasPhone={Boolean(lead.phone)}
          />

          {/* Tabbed Workspace */}
          <div className="space-y-4">
            <div className="flex border-b border-border">
              <button
                type="button"
                onClick={() => setActiveTab("audit")}
                className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === "audit"
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                Audit
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("analysis")}
                className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === "analysis"
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                Analysis
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("whatsapp")}
                className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === "whatsapp"
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                WhatsApp
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("tasks")}
                className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === "tasks"
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                Tasks
              </button>
            </div>

            {/* Tab: Audit */}
            {activeTab === "audit" && (
              <AuditReport
                audit={auditReport?.audit ?? lead.audit}
                evidence={auditReport?.evidence ?? lead.evidence ?? []}
                desktopScreenshotUrl={auditReport?.signed_screenshot_desktop_url}
                mobileScreenshotUrl={auditReport?.signed_screenshot_mobile_url}
                websiteUrl={lead.website_url}
                isAuditing={isAuditing || lead.audit?.status === "running"}
                onStartAudit={handleStartAudit}
              />
            )}

            {/* Tab: Analysis */}
            {activeTab === "analysis" && (
              <div className="space-y-4">
                {analysisError && (
                  <div className="flex items-center gap-2 rounded-lg border border-problem/30 bg-problem/10 p-3 text-xs text-problem">
                    <AlertCircle className="size-4 shrink-0" />
                    <span>{analysisError}</span>
                  </div>
                )}
                <AIAnalysis
                  analysis={analysis}
                  isLoading={isLoadingAnalysis}
                  isRunning={isRunningAnalysis}
                  onRunAnalysis={handleStartAnalysis}
                />
              </div>
            )}

            {/* Tab: WhatsApp */}
            {activeTab === "whatsapp" && (
              <div className="rounded-lg border border-border bg-card p-6 text-center">
                <Smartphone className="mx-auto size-8 text-muted-foreground" />
                <h3 className="mt-2 text-sm font-medium text-foreground">
                  WhatsApp outreach workspace
                </h3>
                <p className="mt-1 text-xs text-muted-foreground max-w-sm mx-auto">
                  Review generated message drafts, manage conversation threads, and send follow-ups.
                </p>
                <Button variant="outline" size="sm" className="mt-4" disabled>
                  Outreach available in Stage 5
                </Button>
              </div>
            )}

            {/* Tab: Tasks */}
            {activeTab === "tasks" && (
              <div className="rounded-lg border border-border bg-card p-6 text-center">
                <Clock className="mx-auto size-8 text-muted-foreground" />
                <h3 className="mt-2 text-sm font-medium text-foreground">Tasks and activity</h3>
                <p className="mt-1 text-xs text-muted-foreground max-w-sm mx-auto">
                  Scheduled follow-ups, meeting preparations, and audit review tasks will appear here.
                </p>
                <p className="mt-4 text-xs text-muted-foreground">No active tasks for this lead.</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Sticky Column */}
        <div className="space-y-6">
          {/* Next Step Panel */}
          <div className="rounded-lg border border-border bg-card p-5 space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Recommended next step
            </h3>
            <div>
              <p className="text-sm font-medium text-foreground">{nextStep.title}</p>
              <p className="mt-1 text-xs text-muted-foreground">{nextStep.description}</p>
            </div>
            {nextStep.buttonText && (
              <Button
                variant="default"
                size="sm"
                className="w-full"
                onClick={() => {
                  if (nextStep.tab) {
                    setActiveTab(nextStep.tab);
                  }
                  if (nextStep.action === "audit") {
                    handleStartAudit();
                  } else if (nextStep.action === "analysis") {
                    handleStartAnalysis();
                  }
                }}
                disabled={isAuditing || auditStatus === "running" || isRunningAnalysis}
              >
                {nextStep.buttonText}
              </Button>
            )}
          </div>

          {/* Contact Details Card */}
          <div className="rounded-lg border border-border bg-card p-5 space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Contact information
            </h3>
            <div className="space-y-3 text-sm">
              <div className="flex items-start gap-2.5">
                <Phone className="size-4 shrink-0 text-muted-foreground mt-0.5" />
                <div>
                  <span className="text-xs text-muted-foreground block">Phone</span>
                  {lead.phone ? (
                    <a
                      href={`tel:${safePhone}`}
                      className="text-foreground hover:text-primary transition-colors tabular-nums"
                    >
                      {lead.phone}
                    </a>
                  ) : (
                    <span className="text-muted-foreground text-xs">Not listed</span>
                  )}
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <Mail className="size-4 shrink-0 text-muted-foreground mt-0.5" />
                <div>
                  <span className="text-xs text-muted-foreground block">Email</span>
                  {lead.email ? (
                    <a
                      href={`mailto:${safeEmail}`}
                      className="text-foreground hover:text-primary transition-colors"
                    >
                      {lead.email}
                    </a>
                  ) : (
                    <span className="text-muted-foreground text-xs">Not listed</span>
                  )}
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <Globe className="size-4 shrink-0 text-muted-foreground mt-0.5" />
                <div>
                  <span className="text-xs text-muted-foreground block">Website</span>
                  {safeWebsiteUrl ? (
                    <a
                      href={safeWebsiteUrl}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="text-primary hover:underline break-all"
                    >
                      {lead.website_url}
                    </a>
                  ) : (
                    <span className="text-muted-foreground text-xs">
                      {lead.website_url ? "Invalid website URL" : "Not listed"}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <MapPin className="size-4 shrink-0 text-muted-foreground mt-0.5" />
                <div>
                  <span className="text-xs text-muted-foreground block">Address</span>
                  {lead.address ? (
                    <a
                      href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                        `${lead.business_name} ${lead.address}`
                      )}`}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="text-foreground hover:text-primary transition-colors block text-xs"
                    >
                      {lead.address}
                    </a>
                  ) : (
                    <span className="text-muted-foreground text-xs">Not listed</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LeadDetailPage({
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
          <div className="h-48 bg-card border border-border rounded-md animate-pulse" />
        </div>
      }
    >
      <LeadDetailContent params={params} />
    </Suspense>
  );
}
