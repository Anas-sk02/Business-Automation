"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { SuppressionRecord, SuppressionListResponse } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ShieldCheck, Search, Phone, ChevronLeft, ChevronRight, RefreshCw, AlertCircle } from "lucide-react";

export function formatIndianPhone(rawPhone: string | null | undefined): string {
  if (!rawPhone) return "—";
  const cleaned = rawPhone.trim();
  // e.g. +919822012345 -> +91 98220 12345
  if (cleaned.startsWith("+91") && cleaned.length === 13) {
    return `+91 ${cleaned.slice(3, 8)} ${cleaned.slice(8)}`;
  }
  return cleaned;
}

export function getSafeTelHref(phone: string | null | undefined): string {
  if (!phone) return "#";
  const sanitized = phone.replace(/[^0-9+]/g, "");
  const digitCount = (sanitized.match(/\d/g) || []).length;
  return digitCount >= 7 ? `tel:${sanitized}` : "#";
}

export function formatIndianDate(isoDate: string | null | undefined): string {
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

export function SuppressionTable() {
  const [records, setRecords] = useState<SuppressionRecord[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 20;
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [activeSearch, setActiveSearch] = useState<string>("");

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSuppressionList = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    const queryParams = new URLSearchParams();
    queryParams.set("page", page.toString());
    queryParams.set("page_size", pageSize.toString());
    if (activeSearch.trim()) {
      queryParams.set("search", activeSearch.trim());
    }

    try {
      const res = await api.get<{ data: SuppressionListResponse }>(
        `/api/settings/suppression-list?${queryParams.toString()}`
      );
      if (res?.data) {
        setRecords(Array.isArray(res.data.suppressed_contacts) ? res.data.suppressed_contacts : []);
        setTotal(typeof res.data.total === "number" ? res.data.total : 0);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load suppression list";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, activeSearch]);

  useEffect(() => {
    let ignore = false;
    async function init() {
      const queryParams = new URLSearchParams();
      queryParams.set("page", page.toString());
      queryParams.set("page_size", pageSize.toString());
      if (activeSearch.trim()) {
        queryParams.set("search", activeSearch.trim());
      }

      try {
        const res = await api.get<{ data: SuppressionListResponse }>(
          `/api/settings/suppression-list?${queryParams.toString()}`
        );
        if (!ignore && res?.data) {
          setRecords(Array.isArray(res.data.suppressed_contacts) ? res.data.suppressed_contacts : []);
          setTotal(typeof res.data.total === "number" ? res.data.total : 0);
          setError(null);
        }
      } catch (err: unknown) {
        if (!ignore) {
          const msg = err instanceof Error ? err.message : "Failed to load suppression list";
          setError(msg);
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    init();
    return () => {
      ignore = true;
    };
  }, [page, pageSize, activeSearch]);

  // Handle Search Submission
  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setActiveSearch(searchQuery);
  }

  const totalPages = Math.max(Math.ceil(total / pageSize), 1);

  return (
    <Card className="border border-border">
      <CardHeader className="pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <CardTitle className="text-base font-semibold text-foreground">
                Suppression Safeguard List
              </CardTitle>
              <Badge variant="outline" className="text-[11px] font-medium text-caution border-caution/40 bg-caution/10">
                Permanent lock
              </Badge>
            </div>
            <CardDescription className="text-xs text-muted-foreground mt-0.5">
              Read-only record of opted-out phone numbers permanently excluded from all campaigns
            </CardDescription>
          </div>

          <div className="text-xs font-medium text-muted-foreground tabular-nums">
            Total suppressed: <span className="font-semibold text-foreground">{total.toLocaleString("en-IN")}</span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Safeguard Assurance Banner */}
        <div className="p-3.5 rounded-md border border-border bg-muted/40 flex items-start gap-3 text-xs text-muted-foreground">
          <ShieldCheck className="w-4 h-4 text-good shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <p className="font-medium text-foreground">
              Anti-spam and opt-out guarantee
            </p>
            <p>
              When a recipient replies STOP or asks to opt out, they are instantly recorded here.
              Every message generation and dispatch check queries this list to ensure no further outreach is ever attempted.
            </p>
          </div>
        </div>

        {/* Search Bar */}
        <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 max-w-md">
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by phone, business, or campaign..."
              className="pl-8 h-9 text-xs"
            />
          </div>
          <Button type="submit" variant="outline" size="sm" className="h-9 px-3 text-xs shrink-0">
            Search
          </Button>
          {activeSearch && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setSearchQuery("");
                setActiveSearch("");
                setPage(1);
              }}
              className="h-9 px-2 text-xs text-muted-foreground hover:text-foreground"
            >
              Clear
            </Button>
          )}
        </form>

        {/* Error State */}
        {error && !isLoading && (
          <div className="p-3 rounded-md border border-problem/30 bg-problem-soft text-problem flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
            <Button variant="ghost" size="sm" onClick={fetchSuppressionList} className="h-7 px-2 text-xs">
              <RefreshCw className="w-3 h-3 mr-1" />
              Retry
            </Button>
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-10 w-full rounded" />
            ))}
          </div>
        )}

        {/* Loaded Table */}
        {!isLoading && !error && (
          <>
            {records.length === 0 ? (
              <div className="p-8 text-center border border-dashed border-border rounded-md space-y-1">
                <p className="text-sm font-medium text-foreground">
                  {activeSearch
                    ? "No suppressed contacts match your search."
                    : "No opted-out contacts yet."}
                </p>
                <p className="text-xs text-muted-foreground">
                  {activeSearch
                    ? "Try searching by a different phone number or campaign name."
                    : "Contacts who opt out or reply STOP will appear here automatically."}
                </p>
              </div>
            ) : (
              <div className="border border-border rounded-md overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/50 border-b border-border">
                    <tr className="text-muted-foreground font-medium">
                      <th className="py-2.5 px-4">Suppressed Phone</th>
                      <th className="py-2.5 px-4">Business</th>
                      <th className="py-2.5 px-4">Originating Campaign</th>
                      <th className="py-2.5 px-4">Reason</th>
                      <th className="py-2.5 px-4 text-right">Opted Out</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60 text-foreground">
                    {records.map((item) => (
                      <tr key={item.id} className="hover:bg-muted/20">
                        <td className="py-2.5 px-4 font-mono">
                          <a
                            href={getSafeTelHref(item.phone)}
                            className="inline-flex items-center gap-1.5 text-foreground hover:text-primary transition-colors font-medium tabular-nums"
                          >
                            <Phone className="w-3 h-3 text-muted-foreground" />
                            <span>{formatIndianPhone(item.phone)}</span>
                          </a>
                        </td>
                        <td className="py-2.5 px-4 text-foreground font-medium max-w-[160px] truncate">
                          {item.business_name || <span className="text-muted-foreground font-normal">Not listed</span>}
                        </td>
                        <td className="py-2.5 px-4">
                          <span className="inline-block px-2 py-0.5 rounded text-[11px] bg-muted text-foreground border border-border/80 max-w-[180px] truncate">
                            {item.campaign_name}
                          </span>
                        </td>
                        <td className="py-2.5 px-4">
                          <Badge variant="secondary" className="text-[10px] font-normal">
                            {item.suppression_reason || "Opted out"}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-4 text-right tabular-nums text-muted-foreground">
                          {formatIndianDate(item.opted_out_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between text-xs text-muted-foreground pt-2">
                <span>
                  Showing page {page} of {totalPages} ({total} contacts)
                </span>
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(p - 1, 1))}
                    className="h-8 px-2.5 text-xs"
                  >
                    <ChevronLeft className="w-3.5 h-3.5 mr-0.5" />
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                    className="h-8 px-2.5 text-xs"
                  >
                    Next
                    <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

