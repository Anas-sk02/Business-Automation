"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import {
  INDUSTRY_TEMPLATES,
  STANDARD_OPPORTUNITY_SIGNALS,
  getIndustryTemplate,
} from "@/lib/industry-templates";
import type { CreateCampaignInput, ResponseEnvelope, Campaign } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Loader2,
} from "lucide-react";

const STANDARD_SERVICES = [
  "Website Development",
  "Website Redesign",
  "Digital Marketing",
  "SEO & Local Search",
  "Custom Service",
];

export default function NewCampaignPage() {
  const router = useRouter();

  // Form State
  const [name, setName] = useState("");
  const [selectedIndustryId, setSelectedIndustryId] = useState("coaching_institutes");
  const [customIndustryLabel, setCustomIndustryLabel] = useState("");
  const [location, setLocation] = useState("");
  const [keywordsInput, setKeywordsInput] = useState("");
  const [targetLeads, setTargetLeads] = useState<number>(50);
  const [minRating, setMinRating] = useState<number>(0.0);

  const [serviceOffered, setServiceOffered] = useState("Website Development");
  const [customService, setCustomService] = useState("");

  const [selectedSignals, setSelectedSignals] = useState<string[]>([
    "no_website",
    "mobile_issues",
    "missing_form",
    "missing_whatsapp",
  ]);

  const [followupGapDays, setFollowupGapDays] = useState<number>(3);
  const [maxFollowups, setMaxFollowups] = useState<number>(3);
  const [quietHoursStart, setQuietHoursStart] = useState("21:00");
  const [quietHoursEnd, setQuietHoursEnd] = useState("09:00");
  const [maxBudget, setMaxBudget] = useState<string>("0");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const currentTemplate = getIndustryTemplate(selectedIndustryId);
  const isCustomIndustry = selectedIndustryId === "custom";

  const handleSignalToggle = (signalId: string) => {
    setSelectedSignals((prev) =>
      prev.includes(signalId)
        ? prev.filter((id) => id !== signalId)
        : [...prev, signalId]
    );
  };

  const handleIndustryChange = (newId: string) => {
    setSelectedIndustryId(newId);
    const template = getIndustryTemplate(newId);
    if (newId !== "custom" && template.defaultKeywords.length > 0) {
      setKeywordsInput(template.defaultKeywords.join(", "));
    }
  };

  const handleSubmit = async (startDiscoveryImmediately: boolean) => {
    setErrorMessage(null);

    // Validation
    if (!name.trim()) {
      setErrorMessage("Please enter a campaign name.");
      return;
    }
    if (!location.trim()) {
      setErrorMessage("Please enter a city or target area.");
      return;
    }
    if (isCustomIndustry && !customIndustryLabel.trim()) {
      setErrorMessage("Please type your custom industry label.");
      return;
    }

    const industryLabel = isCustomIndustry
      ? customIndustryLabel.trim()
      : currentTemplate.label;

    const parsedBudget = parseFloat(maxBudget) || 0;
    if (parsedBudget < 0) {
      setErrorMessage("Maximum budget cannot be negative.");
      return;
    }

    const parsedTargetLeads = Number(targetLeads) || 50;
    if (parsedTargetLeads < 1 || parsedTargetLeads > 500) {
      setErrorMessage("Target leads must be between 1 and 500.");
      return;
    }

    const parsedFollowupGap = Number(followupGapDays) || 3;
    if (parsedFollowupGap < 1 || parsedFollowupGap > 30) {
      setErrorMessage("Follow-up gap must be between 1 and 30 days.");
      return;
    }

    const parsedMaxFollowups = Number(maxFollowups) || 0;
    if (parsedMaxFollowups < 0 || parsedMaxFollowups > 5) {
      setErrorMessage("Maximum follow-ups must be between 0 and 5.");
      return;
    }

    const timeRegex = /^([01]\d|2[0-3]):[0-5]\d$/;
    if (quietHoursStart && !timeRegex.test(quietHoursStart)) {
      setErrorMessage("Quiet hours start must be in HH:MM format.");
      return;
    }
    if (quietHoursEnd && !timeRegex.test(quietHoursEnd)) {
      setErrorMessage("Quiet hours end must be in HH:MM format.");
      return;
    }

    const parsedKeywords = keywordsInput
      .split(/[,;\n]+/)
      .map((k) => k.trim())
      .filter((k) => k.length > 0);

    const effectiveService =
      serviceOffered === "Custom Service" && customService.trim()
        ? customService.trim()
        : serviceOffered;

    const payload: CreateCampaignInput = {
      name: name.trim(),
      industry: selectedIndustryId,
      industry_label: industryLabel,
      location: location.trim(),
      keywords: parsedKeywords,
      target_leads: parsedTargetLeads,
      min_rating: Number(minRating) || 0.0,
      service_offered: effectiveService,
      signals: selectedSignals,
      whatsapp_settings: {
        auto_send_after_approval: false,
        followup_gap_days: parsedFollowupGap,
        max_followups: parsedMaxFollowups,
        quiet_hours_start: quietHoursStart || "21:00",
        quiet_hours_end: quietHoursEnd || "09:00",
      },
      max_budget: parsedBudget,
    };

    setIsSubmitting(true);

    try {
      const response = await api.post<ResponseEnvelope<Campaign>>(
        "/api/campaigns",
        payload
      );

      const createdCampaign = response?.data;
      if (!createdCampaign?.id) {
        throw new Error("Invalid response received from server");
      }

      if (startDiscoveryImmediately) {
        router.push(`/campaigns/${createdCampaign.id}`);
      } else {
        router.push("/campaigns");
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Failed to create campaign. Please check inputs and server connection.";
      setErrorMessage(msg);
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto pb-28 space-y-8">
      {/* Header & Back link */}
      <div className="space-y-2">
        <Link
          href="/campaigns"
          className="inline-flex items-center text-xs text-muted-foreground hover:text-foreground transition-colors -ml-1"
        >
          <ArrowLeft className="mr-1 h-3.5 w-3.5" />
          Back to campaigns
        </Link>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            New campaign
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Configure your local business search criteria, opportunity signals, and messaging limits
          </p>
        </div>
      </div>

      {/* Global Form Error Notice */}
      {errorMessage && (
        <div className="p-4 rounded-md bg-problem-soft border border-problem/30 text-problem flex items-center gap-2 text-sm">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Section 1: Who to find */}
      <section className="p-6 rounded-md bg-card border border-border space-y-6">
        <div className="border-b border-border pb-3">
          <h2 className="text-base font-semibold text-foreground">
            1. Who to find
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Target industry, location, keywords, and volume of leads
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="camp-name">
              Campaign name <span className="text-problem">*</span>
            </Label>
            <Input
              id="camp-name"
              placeholder="e.g. Nagpur Coaching Centers Q4"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9"
            />
            <p className="text-[11px] text-muted-foreground">
              A recognizable title for organizing your work queue
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="camp-industry">
              Industry <span className="text-problem">*</span>
            </Label>
            <select
              id="camp-industry"
              value={selectedIndustryId}
              onChange={(e) => handleIndustryChange(e.target.value)}
              className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground"
            >
              {INDUSTRY_TEMPLATES.map((t) => (
                <option key={t.id} value={t.id} className="bg-card text-foreground">
                  {t.icon} {t.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="camp-location">
              City or target area <span className="text-problem">*</span>
            </Label>
            <Input
              id="camp-location"
              placeholder="e.g. Pune, Maharashtra"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="h-9"
            />
          </div>

          {isCustomIndustry && (
            <div className="space-y-1.5 md:col-span-2">
              <Label htmlFor="camp-custom-industry">
                Custom industry title <span className="text-problem">*</span>
              </Label>
              <Input
                id="camp-custom-industry"
                placeholder="e.g. Interior Designers & Architects"
                value={customIndustryLabel}
                onChange={(e) => setCustomIndustryLabel(e.target.value)}
                className="h-9"
              />
            </div>
          )}

          {/* Real Industry Template Summary per UI-UX.md Section 6.4 */}
          <div className="md:col-span-2 p-3 rounded-md bg-secondary border border-border/60 text-xs text-foreground flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
            <span className="leading-relaxed">
              {currentTemplate.summaryChecks}
            </span>
          </div>

          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="camp-keywords">Additional search keywords (Optional)</Label>
            <Input
              id="camp-keywords"
              placeholder="Comma-separated: IIT JEE, NEET, foundation classes"
              value={keywordsInput}
              onChange={(e) => setKeywordsInput(e.target.value)}
              className="h-9"
            />
            <p className="text-[11px] text-muted-foreground">
              Added to search query variations for Google Places discovery
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="camp-target-leads">Target leads</Label>
            <Input
              id="camp-target-leads"
              type="number"
              min="1"
              max="500"
              value={targetLeads}
              onChange={(e) => setTargetLeads(parseInt(e.target.value) || 0)}
              className="h-9 tabular-nums"
            />
            <p className="text-[11px] text-muted-foreground">
              Maximum businesses to collect in this run (Default: 50)
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="camp-min-rating">Minimum Google rating (Optional)</Label>
            <select
              id="camp-min-rating"
              value={minRating}
              onChange={(e) => setMinRating(parseFloat(e.target.value))}
              className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground"
            >
              <option value="0.0" className="bg-card text-foreground">Any rating (0.0+)</option>
              <option value="3.0" className="bg-card text-foreground">3.0 stars and above</option>
              <option value="3.5" className="bg-card text-foreground">3.5 stars and above</option>
              <option value="4.0" className="bg-card text-foreground">4.0 stars and above</option>
              <option value="4.5" className="bg-card text-foreground">4.5 stars and above</option>
            </select>
          </div>
        </div>
      </section>

      {/* Section 2: What you offer */}
      <section className="p-6 rounded-md bg-card border border-border space-y-4">
        <div className="border-b border-border pb-3">
          <h2 className="text-base font-semibold text-foreground">
            2. What you offer
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            The service or product pitch aligned with audited findings
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="camp-service">Service offering</Label>
            <select
              id="camp-service"
              value={serviceOffered}
              onChange={(e) => setServiceOffered(e.target.value)}
              className="w-full h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground"
            >
              {STANDARD_SERVICES.map((s) => (
                <option key={s} value={s} className="bg-card text-foreground">
                  {s}
                </option>
              ))}
            </select>
          </div>

          {serviceOffered === "Custom Service" && (
            <div className="space-y-1.5">
              <Label htmlFor="camp-custom-service">Specify custom service</Label>
              <Input
                id="camp-custom-service"
                placeholder="e.g. WhatsApp Automation Bot"
                value={customService}
                onChange={(e) => setCustomService(e.target.value)}
                className="h-9"
              />
            </div>
          )}
        </div>
      </section>

      {/* Section 3: What to look for */}
      <section className="p-6 rounded-md bg-card border border-border space-y-4">
        <div className="border-b border-border pb-3">
          <h2 className="text-base font-semibold text-foreground">
            3. What to look for
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Opportunity signals evaluated during website audits and AI analysis
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
          {STANDARD_OPPORTUNITY_SIGNALS.map((signal) => {
            const isChecked = selectedSignals.includes(signal.id);
            return (
              <label
                key={signal.id}
                className={`flex items-start gap-3 p-3 rounded-md border cursor-pointer select-none transition-colors ${
                  isChecked
                    ? "bg-secondary/70 border-primary/40 text-foreground"
                    : "bg-card border-border hover:bg-muted/40 text-muted-foreground"
                }`}
              >
                <Checkbox
                  checked={isChecked}
                  onCheckedChange={() => handleSignalToggle(signal.id)}
                  className="mt-0.5"
                />
                <div className="space-y-0.5">
                  <div className="text-xs font-medium text-foreground">
                    {signal.label}
                  </div>
                  <div className="text-[11px] text-muted-foreground leading-relaxed">
                    {signal.description}
                  </div>
                </div>
              </label>
            );
          })}
        </div>
      </section>

      {/* Section 4: Messaging and limits */}
      <section className="p-6 rounded-md bg-card border border-border space-y-6">
        <div className="border-b border-border pb-3">
          <h2 className="text-base font-semibold text-foreground">
            4. Messaging and limits
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Quiet hours, follow-up parameters, and campaign budget
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="camp-gap">Follow-up gap (days)</Label>
            <Input
              id="camp-gap"
              type="number"
              min="1"
              max="30"
              value={followupGapDays}
              onChange={(e) => setFollowupGapDays(parseInt(e.target.value) || 1)}
              className="h-9 tabular-nums"
            />
            <p className="text-[11px] text-muted-foreground">
              Days to wait before scheduling follow-up drafts (Default: 3)
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="camp-max-followups">Maximum follow-ups</Label>
            <Input
              id="camp-max-followups"
              type="number"
              min="0"
              max="5"
              value={maxFollowups}
              onChange={(e) => setMaxFollowups(parseInt(e.target.value) || 0)}
              className="h-9 tabular-nums"
            />
            <p className="text-[11px] text-muted-foreground">
              Maximum follow-up messages per lead before closing (Default: 3, Max: 5)
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="camp-quiet-start">Quiet hours start (IST)</Label>
            <Input
              id="camp-quiet-start"
              type="time"
              value={quietHoursStart}
              onChange={(e) => setQuietHoursStart(e.target.value)}
              className="h-9 tabular-nums"
            />
            <p className="text-[11px] text-muted-foreground">
              Default 21:00 (9:00 PM IST)
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="camp-quiet-end">Quiet hours end (IST)</Label>
            <Input
              id="camp-quiet-end"
              type="time"
              value={quietHoursEnd}
              onChange={(e) => setQuietHoursEnd(e.target.value)}
              className="h-9 tabular-nums"
            />
            <p className="text-[11px] text-muted-foreground">
              Default 09:00 (9:00 AM IST)
            </p>
          </div>

          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="camp-budget">Maximum budget (₹ INR)</Label>
            <Input
              id="camp-budget"
              type="number"
              min="0"
              step="50"
              placeholder="0 (No limit)"
              value={maxBudget}
              onChange={(e) => setMaxBudget(e.target.value)}
              className="h-9 tabular-nums"
            />
            {/* Caution banner when budget is empty or zero per UI-UX.md Section 6.4 */}
            {(parseFloat(maxBudget) <= 0 || !maxBudget) && (
              <div className="mt-2 p-2.5 rounded-md bg-caution-soft border border-caution/30 text-caution flex items-center gap-2 text-xs">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>No budget set. Spending will not be capped.</span>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Sticky Footer Actions per UI-UX.md Section 5.6 & 6.4 */}
      <div className="fixed bottom-0 left-0 right-0 z-20 border-t border-border bg-card/95 backdrop-blur-xs py-3 px-6 shadow-md">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link href="/campaigns">
            <Button variant="ghost" size="sm" className="h-9 text-xs">
              Cancel
            </Button>
          </Link>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              disabled={isSubmitting}
              onClick={() => handleSubmit(false)}
              className="h-9 text-xs"
            >
              {isSubmitting ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : null}
              Save draft
            </Button>
            <Button
              disabled={isSubmitting}
              onClick={() => handleSubmit(true)}
              className="h-9 text-xs"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  Creating...
                </>
              ) : (
                "Save & open campaign"
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
