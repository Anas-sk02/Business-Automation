"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Maximize2, Image as ImageIcon } from "lucide-react";

export interface ScreenshotViewerProps {
  desktopUrl?: string | null;
  mobileUrl?: string | null;
  testedUrl?: string | null;
  capturedAt?: string | null;
  className?: string;
}

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

export function ScreenshotViewer({
  desktopUrl,
  mobileUrl,
  testedUrl,
  capturedAt,
  className = "",
}: ScreenshotViewerProps) {
  const [enlarged, setEnlarged] = useState<{
    url: string;
    label: string;
    width: string;
  } | null>(null);

  const safeDesktopUrl = sanitizeUrl(desktopUrl);
  const safeMobileUrl = sanitizeUrl(mobileUrl);
  const hasAnyScreenshot = Boolean(safeDesktopUrl || safeMobileUrl);

  const dateObj = capturedAt ? new Date(capturedAt) : null;
  const formattedDate =
    dateObj && !Number.isNaN(dateObj.getTime())
      ? dateObj.toLocaleString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
      : "Not recorded";

  if (!hasAnyScreenshot) {
    return (
      <div className={`rounded-md border border-border/60 bg-muted/10 p-5 text-center ${className}`}>
        <ImageIcon className="mx-auto size-7 text-muted-foreground mb-1.5" />
        <p className="text-xs font-medium text-foreground">No screenshots available</p>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          Screenshots will be captured automatically during the next website audit.
        </p>
      </div>
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Visual evidence
        </h4>
        <span className="text-[11px] text-muted-foreground">Click to enlarge</span>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Desktop Screenshot Frame (4px radius, 1px line, flat frame per UI-UX.md §5.4) */}
        <div className="rounded border border-border bg-card overflow-hidden">
          <div className="flex items-center justify-between border-b border-border/60 bg-muted/30 px-3 py-1.5 text-xs">
            <span className="font-medium text-foreground">Desktop view</span>
            <span className="text-muted-foreground text-[11px]">1280 px wide</span>
          </div>
          {safeDesktopUrl ? (
            <button
              type="button"
              onClick={() =>
                setEnlarged({
                  url: safeDesktopUrl,
                  label: "Desktop view",
                  width: "1280 px",
                })
              }
              className="group relative block w-full aspect-video bg-muted/20 overflow-hidden text-left cursor-zoom-in"
            >
              <img
                src={safeDesktopUrl}
                alt="Desktop website screenshot"
                className="w-full h-full object-cover object-top transition-transform duration-200 group-hover:scale-[1.02]"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-black/0 transition-colors group-hover:bg-black/10 flex items-center justify-center">
                <span className="opacity-0 group-hover:opacity-100 transition-opacity rounded bg-card/90 px-2 py-1 text-[11px] font-medium text-foreground shadow-sm flex items-center gap-1">
                  <Maximize2 className="size-3" /> Enlarge
                </span>
              </div>
            </button>
          ) : (
            <div className="aspect-video flex items-center justify-center text-xs text-muted-foreground bg-muted/10">
              Desktop capture not available
            </div>
          )}
        </div>

        {/* Mobile Screenshot Frame (4px radius, 1px line, flat frame per UI-UX.md §5.4) */}
        <div className="rounded border border-border bg-card overflow-hidden">
          <div className="flex items-center justify-between border-b border-border/60 bg-muted/30 px-3 py-1.5 text-xs">
            <span className="font-medium text-foreground">Mobile view</span>
            <span className="text-muted-foreground text-[11px]">375 px wide</span>
          </div>
          {safeMobileUrl ? (
            <button
              type="button"
              onClick={() =>
                setEnlarged({
                  url: safeMobileUrl,
                  label: "Mobile view",
                  width: "375 px",
                })
              }
              className="group relative block w-full aspect-video bg-muted/20 overflow-hidden text-left cursor-zoom-in"
            >
              <img
                src={safeMobileUrl}
                alt="Mobile website screenshot"
                className="w-full h-full object-cover object-top transition-transform duration-200 group-hover:scale-[1.02]"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-black/0 transition-colors group-hover:bg-black/10 flex items-center justify-center">
                <span className="opacity-0 group-hover:opacity-100 transition-opacity rounded bg-card/90 px-2 py-1 text-[11px] font-medium text-foreground shadow-sm flex items-center gap-1">
                  <Maximize2 className="size-3" /> Enlarge
                </span>
              </div>
            </button>
          ) : (
            <div className="aspect-video flex items-center justify-center text-xs text-muted-foreground bg-muted/10">
              Mobile capture not available
            </div>
          )}
        </div>
      </div>

      {/* Enlargement Dialog with Capture Time & Tested URL */}
      {enlarged && (
        <Dialog open={Boolean(enlarged)} onOpenChange={() => setEnlarged(null)}>
          <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col p-6">
            <DialogHeader className="space-y-1">
              <DialogTitle className="text-base font-semibold text-foreground">
                {enlarged.label} ({enlarged.width})
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                Captured on {formattedDate}
                {testedUrl ? ` · Tested URL: ${testedUrl}` : ""}
              </DialogDescription>
            </DialogHeader>
            <div className="mt-3 flex-1 overflow-auto rounded border border-border bg-muted/10 p-2">
              <img
                src={enlarged.url}
                alt={`${enlarged.label} enlarged view`}
                className="w-full h-auto object-contain mx-auto"
              />
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
