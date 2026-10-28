"use client";

import React, { useState, useEffect, useCallback, useTransition, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Globe,
  Phone,
  PhoneOff,
  ExternalLink,
  Star,
  Check,
  RotateCcw,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

import { api, ApiClientError } from "@/lib/api";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import type { Lead, PaginatedEnvelope, PipelineStage } from "@/types";

export type StageTone = "neutral" | "petrol" | "good" | "closed";

export interface StageChipInfo {
  label: string;
  tone: StageTone;
  dotClass: string;
  badgeClass: string;
}

/**
 * Returns stage display name and 4-tone styling per docs/UI-UX.md Section 5.2.
 */
export function getStageChipInfo(stage: PipelineStage | string): StageChipInfo {
  const norm = String(stage || "").toLowerCase();
  switch (norm) {
    case "discovered":
      return {
        label: "Discovered",
        tone: "neutral",
        dotClass: "bg-muted-foreground",
        badgeClass: "border-border text-foreground bg-muted/40",
      };
    case "research_pending":
      return {
        label: "Research pending",
        tone: "neutral",
        dotClass: "bg-muted-foreground",
        badgeClass: "border-border text-foreground bg-muted/40",
      };
    case "researched":
      return {
        label: "Researched",
        tone: "neutral",
        dotClass: "bg-muted-foreground",
        badgeClass: "border-border text-foreground bg-muted/40",
      };
    case "qualified":
      return {
        label: "Qualified",
        tone: "petrol",
        dotClass: "bg-primary",
        badgeClass: "border-primary/40 text-primary bg-primary/10",
      };
    case "contacted":
      return {
        label: "Contacted",
        tone: "petrol",
        dotClass: "bg-primary",
        badgeClass: "border-primary/40 text-primary bg-primary/10",
      };
    case "followup_due":
      return {
        label: "Follow-up due",
        tone: "petrol",
        dotClass: "bg-primary",
        badgeClass: "border-primary/40 text-primary bg-primary/10",
      };
    case "replied":
      return {
        label: "Replied",
        tone: "petrol",
        dotClass: "bg-primary",
        badgeClass: "border-primary/40 text-primary bg-primary/10",
      };
    case "interested":
      return {
        label: "Interested",
        tone: "good",
        dotClass: "bg-good",
        badgeClass: "border-good/40 text-good bg-good/10",
      };
    case "meeting_scheduled":
      return {
        label: "Meeting scheduled",
        tone: "good",
        dotClass: "bg-good",
        badgeClass: "border-good/40 text-good bg-good/10",
      };
    case "proposal_sent":
      return {
        label: "Proposal sent",
        tone: "good",
        dotClass: "bg-good",
        badgeClass: "border-good/40 text-good bg-good/10",
      };
    case "negotiation":
      return {
        label: "Negotiation",
        tone: "good",
        dotClass: "bg-good",
        badgeClass: "border-good/40 text-good bg-good/10",
      };
    case "won":
      return {
        label: "Won",
        tone: "good",
        dotClass: "bg-good",
        badgeClass: "border-good/40 text-good bg-good/10",
      };
    case "not_interested":
      return {
        label: "Not interested",
        tone: "closed",
        dotClass: "bg-muted-foreground/60",
        badgeClass: "border-border text-muted-foreground bg-muted/20",
      };
    case "no_response":
      return {
        label: "No response",
        tone: "closed",
        dotClass: "bg-muted-foreground/60",
        badgeClass: "border-border text-muted-foreground bg-muted/20",
      };
    case "closed_lost":
      return {
        label: "Closed lost",
        tone: "closed",
        dotClass: "bg-problem/70",
        badgeClass: "border-problem/30 text-problem/90 bg-problem/10",
      };
    case "opted_out":
      return {
        label: "Opted out",
        tone: "closed",
        dotClass: "bg-problem/70",
        badgeClass: "border-problem/30 text-problem/90 bg-problem/10",
      };
    default:
      return {
        label: norm ? norm.replace(/_/g, " ") : "Unknown",
        tone: "neutral",
        dotClass: "bg-muted-foreground",
        badgeClass: "border-border text-foreground bg-muted/40",
      };
  }
}

export const CANONICAL_STAGES: { id: PipelineStage; label: string }[] = [
  { id: "discovered", label: "Discovered" },
  { id: "research_pending", label: "Research pending" },
  { id: "researched", label: "Researched" },
  { id: "qualified", label: "Qualified" },
  { id: "contacted", label: "Contacted" },
  { id: "followup_due", label: "Follow-up due" },
  { id: "replied", label: "Replied" },
  { id: "interested", label: "Interested" },
  { id: "meeting_scheduled", label: "Meeting scheduled" },
  { id: "proposal_sent", label: "Proposal sent" },
  { id: "negotiation", label: "Negotiation" },
  { id: "won", label: "Won" },
  { id: "not_interested", label: "Not interested" },
  { id: "no_response", label: "No response" },
  { id: "closed_lost", label: "Closed lost" },
  { id: "opted_out", label: "Opted out" },
];

/**
 * Safely sanitizes external URL to prevent XSS (blocks javascript:, data:, etc.).
 * Guarantees a safe http or https protocol.
 */
export function formatSafeUrl(url?: string | null): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  if (/^[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/i.test(trimmed)) {
    return `https://${trimmed}`;
  }
  return null;
}

export interface LeadTableProps {
  campaignId: string;
  totalLeadsCount?: number;
  refreshTrigger?: number;
  onLeadClick?: (lead: Lead) => void;
}

type SortField = "fit_score" | "business_name" | "rating" | "created_at";
type SortOrder = "asc" | "desc";

export function LeadTable({
  campaignId,
  totalLeadsCount,
  refreshTrigger = 0,
  onLeadClick,
}: LeadTableProps) {
  const router = useRouter();
  const [, startTransition] = useTransition();

  // Data states
  const [leads, setLeads] = useState<Lead[]>([]);
  const [totalCount, setTotalCount] = useState<number>(totalLeadsCount || 0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef<boolean>(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Pagination state
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(25);

  // Sorting state (default: fit_score descending per UI-UX.md Section 6.5)
  const [sortBy, setSortBy] = useState<SortField>("fit_score");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  // Filtering states
  const [searchInput, setSearchInput] = useState<string>("");
  const [activeSearch, setActiveSearch] = useState<string>("");
  const [stageFilter, setStageFilter] = useState<string>("all");
  const [websiteFilter, setWebsiteFilter] = useState<string>("all"); // all | has_website | no_website
  const [phoneFilter, setPhoneFilter] = useState<string>("all"); // all | has_phone | no_phone
  const [scoreFilter, setScoreFilter] = useState<string>("all"); // all | qualified | under_60

  // Debounce search input changes (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setActiveSearch(searchInput.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Fetch leads handler
  const fetchLeads = useCallback(async () => {
    if (!campaignId) return;

    setLoading(true);
    setError(null);

    const params: Record<string, string | number | boolean | undefined> = {
      page,
      page_size: pageSize,
      sort_by: sortBy,
      sort_order: sortOrder,
    };

    if (activeSearch) {
      params.search = activeSearch;
    }
    if (stageFilter !== "all") {
      params.stage = stageFilter;
    }
    if (websiteFilter === "has_website") {
      params.has_website = true;
    } else if (websiteFilter === "no_website") {
      params.has_website = false;
    }
    if (phoneFilter === "has_phone") {
      params.has_phone = true;
    } else if (phoneFilter === "no_phone") {
      params.has_phone = false;
    }
    if (scoreFilter === "qualified") {
      params.min_score = 60;
    } else if (scoreFilter === "under_60") {
      params.max_score = 59;
    }

    try {
      const response = await api.get<PaginatedEnvelope<Lead>>(
        `/api/campaigns/${campaignId}/leads`,
        params
      );
      if (!isMountedRef.current) return;
      if (response && Array.isArray(response.data)) {
        setLeads(response.data);
        setTotalCount(response.total ?? response.data.length);
      } else {
        setLeads([]);
        setTotalCount(0);
      }
    } catch (err: unknown) {
      if (!isMountedRef.current) return;
      const msg =
        err instanceof ApiClientError
          ? err.message
          : err instanceof Error
          ? err.message
          : "Failed to load leads.";
      setError(msg);
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [
    campaignId,
    page,
    pageSize,
    sortBy,
    sortOrder,
    activeSearch,
    stageFilter,
    websiteFilter,
    phoneFilter,
    scoreFilter,
  ]);

  // Re-fetch on dependencies change or parent trigger
  useEffect(() => {
    fetchLeads();
  }, [fetchLeads, refreshTrigger]);

  // Handle column header sort toggles
  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      // Default to desc for numeric fields, asc for text fields
      setSortOrder(field === "business_name" ? "asc" : "desc");
    }
    setPage(1);
  };

  const hasActiveFilters =
    Boolean(activeSearch) ||
    stageFilter !== "all" ||
    websiteFilter !== "all" ||
    phoneFilter !== "all" ||
    scoreFilter !== "all";

  const handleResetFilters = () => {
    setSearchInput("");
    setActiveSearch("");
    setStageFilter("all");
    setWebsiteFilter("all");
    setPhoneFilter("all");
    setScoreFilter("all");
    setSortBy("fit_score");
    setSortOrder("desc");
    setPage(1);
  };

  const handleRowClick = (lead: Lead) => {
    if (onLeadClick) {
      onLeadClick(lead);
    } else {
      startTransition(() => {
        router.push(`/leads/${lead.id}`);
      });
    }
  };

  // Pagination bounds
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const startItem = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, totalCount);

  return (
    <div className="space-y-4">
      {/* Filter and Search Bar per UI-UX.md Section 6.5 */}
      <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
        {/* Search Input */}
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search by business name..."
            className="h-8 pl-8 text-xs bg-background"
          />
          {searchInput && (
            <button
              onClick={() => setSearchInput("")}
              className="absolute right-2.5 top-2 text-xs text-muted-foreground hover:text-foreground"
              title="Clear search"
            >
              ×
            </button>
          )}
        </div>

        {/* Filter Controls Row */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Stage Filter */}
          <select
            value={stageFilter}
            onChange={(e) => {
              setStageFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by stage"
            className="h-8 rounded-md border border-input bg-background px-2.5 py-1 text-xs text-foreground shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="all">All stages</option>
            {CANONICAL_STAGES.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>

          {/* Website Filter */}
          <select
            value={websiteFilter}
            onChange={(e) => {
              setWebsiteFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by website status"
            className="h-8 rounded-md border border-input bg-background px-2.5 py-1 text-xs text-foreground shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="all">Website: All</option>
            <option value="has_website">Has website</option>
            <option value="no_website">No website</option>
          </select>

          {/* Phone Filter */}
          <select
            value={phoneFilter}
            onChange={(e) => {
              setPhoneFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by phone status"
            className="h-8 rounded-md border border-input bg-background px-2.5 py-1 text-xs text-foreground shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="all">Phone: All</option>
            <option value="has_phone">Has phone</option>
            <option value="no_phone">No phone</option>
          </select>

          {/* Fit Score Filter */}
          <select
            value={scoreFilter}
            onChange={(e) => {
              setScoreFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by fit score"
            className="h-8 rounded-md border border-input bg-background px-2.5 py-1 text-xs text-foreground shadow-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="all">Score: All</option>
            <option value="qualified">Qualified (60+)</option>
            <option value="under_60">Under 60</option>
          </select>

          {/* Clear Filters Button */}
          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleResetFilters}
              className="h-8 px-2 text-xs text-muted-foreground hover:text-foreground"
            >
              <RotateCcw className="mr-1 h-3 w-3" />
              Reset
            </Button>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-3 rounded-md bg-problem-soft border border-problem/30 text-problem text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchLeads}
            className="h-7 text-xs border-problem/40 text-problem hover:bg-problem/10"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Leads Table Container */}
      <div className="rounded-md border border-border bg-card overflow-hidden">
        <Table className="w-full text-xs">
          <TableHeader className="bg-muted/40 sticky top-0 border-b border-border">
            <TableRow className="hover:bg-transparent">
              {/* Business Name Column */}
              <TableHead className="w-[34%] font-medium text-foreground text-left py-2.5">
                <button
                  type="button"
                  onClick={() => handleSort("business_name")}
                  className="inline-flex items-center gap-1 hover:text-primary transition-colors focus-visible:outline-none"
                >
                  <span>Business</span>
                  {sortBy === "business_name" ? (
                    sortOrder === "asc" ? (
                      <ArrowUp className="h-3 w-3 text-primary" />
                    ) : (
                      <ArrowDown className="h-3 w-3 text-primary" />
                    )
                  ) : (
                    <ArrowUpDown className="h-3 w-3 text-muted-foreground/60" />
                  )}
                </button>
              </TableHead>

              {/* Rating Column */}
              <TableHead className="w-[15%] font-medium text-foreground text-left py-2.5">
                <button
                  type="button"
                  onClick={() => handleSort("rating")}
                  className="inline-flex items-center gap-1 hover:text-primary transition-colors focus-visible:outline-none"
                >
                  <span>Rating</span>
                  {sortBy === "rating" ? (
                    sortOrder === "asc" ? (
                      <ArrowUp className="h-3 w-3 text-primary" />
                    ) : (
                      <ArrowDown className="h-3 w-3 text-primary" />
                    )
                  ) : (
                    <ArrowUpDown className="h-3 w-3 text-muted-foreground/60" />
                  )}
                </button>
              </TableHead>

              {/* Contact Channels Column */}
              <TableHead className="w-[20%] font-medium text-foreground text-left py-2.5">
                <span>Contact</span>
              </TableHead>

              {/* Fit Score Column (right aligned per UI-UX.md Section 5.5) */}
              <TableHead className="w-[16%] font-medium text-foreground text-right py-2.5">
                <button
                  type="button"
                  onClick={() => handleSort("fit_score")}
                  className="inline-flex items-center justify-end gap-1 hover:text-primary transition-colors focus-visible:outline-none ml-auto"
                >
                  <span>Fit score</span>
                  {sortBy === "fit_score" ? (
                    sortOrder === "asc" ? (
                      <ArrowUp className="h-3 w-3 text-primary" />
                    ) : (
                      <ArrowDown className="h-3 w-3 text-primary" />
                    )
                  ) : (
                    <ArrowUpDown className="h-3 w-3 text-muted-foreground/60" />
                  )}
                </button>
              </TableHead>

              {/* Pipeline Stage Column */}
              <TableHead className="w-[15%] font-medium text-foreground text-left py-2.5">
                <span>Stage</span>
              </TableHead>
            </TableRow>
          </TableHeader>

          <TableBody>
            {/* Loading Skeleton Rows */}
            {loading && (
              <>
                {Array.from({ length: 6 }).map((_, idx) => (
                  <TableRow key={idx} className="h-11">
                    <TableCell>
                      <div className="space-y-1">
                        <Skeleton className="h-3.5 w-40" />
                        <Skeleton className="h-2.5 w-24" />
                      </div>
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-3 w-16" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-3 w-28" />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Skeleton className="h-3 w-6" />
                        <Skeleton className="h-2 w-12 rounded-full" />
                      </div>
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-20 rounded-full" />
                    </TableCell>
                  </TableRow>
                ))}
              </>
            )}

            {/* Empty State: No Leads matching filters */}
            {!loading && leads.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-12 text-center">
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-foreground">
                      {hasActiveFilters
                        ? "No leads match the selected filters."
                        : "No leads discovered yet."}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {hasActiveFilters
                        ? "Try clearing or loosening your search query and filters."
                        : "Start discovery above to find prospective businesses."}
                    </p>
                    {hasActiveFilters && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleResetFilters}
                        className="mt-2 h-7 text-xs"
                      >
                        Reset filters
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            )}

            {/* Render Lead Rows */}
            {!loading &&
              leads.map((lead) => {
                const stageInfo = getStageChipInfo(lead.pipeline_stage);
                const score = lead.fit_score ?? 0;
                const isQualified = score >= 60;
                const clampedScore = Math.min(Math.max(score, 0), 100);

                return (
                  <TableRow
                    key={lead.id}
                    onClick={() => handleRowClick(lead)}
                    className="h-11 border-b border-border/60 hover:bg-primary/5 cursor-pointer transition-colors"
                  >
                    {/* Business Name & Address */}
                    <TableCell className="py-2.5">
                      <div className="min-w-0 pr-2">
                        <div className="font-medium text-foreground truncate text-xs hover:text-primary transition-colors">
                          {lead.business_name}
                        </div>
                        <div className="text-[11px] text-muted-foreground truncate">
                          {lead.address || lead.city || lead.category || "—"}
                        </div>
                      </div>
                    </TableCell>

                    {/* Google Rating & Review Count */}
                    <TableCell className="py-2.5">
                      {lead.rating != null ? (
                        <div className="flex items-center gap-1.5 text-xs text-foreground">
                          <span className="flex items-center gap-0.5 font-medium tabular-nums">
                            <Star className="h-3 w-3 fill-amber-400 text-amber-500" />
                            {lead.rating.toFixed(1)}
                          </span>
                          <span className="text-[11px] text-muted-foreground tabular-nums">
                            ({lead.review_count ?? 0})
                          </span>
                        </div>
                      ) : (
                        <span className="text-[11px] text-muted-foreground">—</span>
                      )}
                    </TableCell>

                    {/* Contact Channels (Phone & Website) */}
                    <TableCell className="py-2.5">
                      <div className="flex items-center gap-2.5 text-[11px]">
                        {/* Phone Badge / Text */}
                        {lead.phone ? (
                          <span
                            className="inline-flex items-center gap-1 text-foreground tabular-nums"
                            title={lead.phone}
                          >
                            <Phone className="h-3 w-3 text-muted-foreground shrink-0" />
                            <span className="truncate max-w-[105px]">{lead.phone}</span>
                          </span>
                        ) : (
                          <span
                            className="inline-flex items-center gap-1 text-muted-foreground/70"
                            title="No phone number: cannot be messaged on WhatsApp"
                          >
                            <PhoneOff className="h-3 w-3 text-muted-foreground/60 shrink-0" />
                            <span>No phone</span>
                          </span>
                        )}

                        {/* Website Link */}
                        {(() => {
                          const safeUrl = formatSafeUrl(lead.website_url);
                          return safeUrl ? (
                            <a
                              href={safeUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex items-center gap-1 text-primary hover:underline shrink-0"
                              title={safeUrl}
                            >
                              <Globe className="h-3 w-3" />
                              <ExternalLink className="h-2.5 w-2.5 opacity-70" />
                            </a>
                          ) : (
                            <span
                              className="text-muted-foreground/60"
                              title="No website found"
                            >
                              —
                            </span>
                          );
                        })()}
                      </div>
                    </TableCell>

                    {/* Fit Score with 48px bar and 60% qualify line per UI-UX.md Section 5.3 */}
                    <TableCell className="py-2.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <span className="text-xs font-semibold tabular-nums text-foreground">
                          {score}
                        </span>
                        <div
                          className="relative w-12 h-2 rounded-full bg-secondary overflow-hidden shrink-0"
                          title={`Lead fit: ${score} of 100 (${
                            isQualified ? "Qualifies" : "Below 60 qualify threshold"
                          })`}
                        >
                          <div
                            className={`h-full transition-all duration-300 ${
                              isQualified ? "bg-primary" : "bg-muted-foreground/40"
                            }`}
                            style={{ width: `${clampedScore}%` }}
                          />
                          {/* Qualify tick line at 60% */}
                          <div
                            className="absolute top-0 bottom-0 left-[60%] w-[1px] bg-background/90"
                            title="Qualifies from 60"
                          />
                        </div>
                      </div>
                    </TableCell>

                    {/* Pipeline Stage Chip per UI-UX.md Section 5.2 */}
                    <TableCell className="py-2.5">
                      <div
                        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium border ${stageInfo.badgeClass}`}
                      >
                        {stageInfo.tone === "good" && lead.pipeline_stage === "won" ? (
                          <Check className="h-2.5 w-2.5 text-good shrink-0" />
                        ) : (
                          <span
                            className={`h-1.5 w-1.5 rounded-full shrink-0 ${stageInfo.dotClass}`}
                          />
                        )}
                        <span>{stageInfo.label}</span>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </Table>
      </div>

      {/* Pagination Footer per UI-UX.md Section 5.5 */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-muted-foreground pt-1">
        <div>
          Showing <span className="font-medium text-foreground tabular-nums">{startItem}</span> to{" "}
          <span className="font-medium text-foreground tabular-nums">{endItem}</span> of{" "}
          <span className="font-medium text-foreground tabular-nums">{totalCount}</span> leads
        </div>

        <div className="flex items-center gap-4">
          {/* Rows per page selector (25, 50 per UI-UX.md Section 5.5) */}
          <div className="flex items-center gap-1.5">
            <span>Rows:</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              aria-label="Rows per page"
              className="h-7 rounded border border-input bg-background px-1.5 text-xs text-foreground focus-visible:outline-none"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </div>

          {/* Page Previous / Next Navigation */}
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1 || loading}
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
              className="h-7 w-7 p-0"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>

            <span className="px-2 text-xs tabular-nums text-foreground">
              {page} / {totalPages}
            </span>

            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages || loading}
              onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
              className="h-7 w-7 p-0"
              aria-label="Next page"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

