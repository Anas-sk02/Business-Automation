"use client";

import { useState } from "react";
import type { WhatsAppDraftResponse, MessageStatus } from "@/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Send,
  RotateCw,
  Save,
  CheckCircle2,
  AlertCircle,
  Eye,
  Edit3,
  Moon,
  ShieldAlert,
} from "lucide-react";

interface MessageDraftEditorProps {
  draft: WhatsAppDraftResponse | null;
  leadId: string;
  leadName: string;
  recipientPhone?: string | null;
  isSuppressed?: boolean;
  suppressionReason?: string | null;
  onSaveDraft: (body: string, status?: MessageStatus) => Promise<void>;
  onApproveAndSend: (currentBody: string, ignoreQuietHours?: boolean) => Promise<void>;
  onRegenerateDraft: (instructions?: string) => Promise<void>;
  isSaving?: boolean;
  isSending?: boolean;
  isRegenerating?: boolean;
}

/**
 * Normalizes phone number display for Indian and international formats.
 */
export function formatPhoneDisplay(phone?: string | null): string {
  if (!phone) return "Not listed";
  const cleaned = phone.replace(/[^\d+]/g, "");
  if (cleaned.startsWith("+91") && cleaned.length === 13) {
    return `+91 ${cleaned.slice(3, 8)} ${cleaned.slice(8)}`;
  }
  return cleaned;
}

/**
 * Checks if current time is within Indian quiet hours (21:00 to 09:00 IST).
 */
export function isIndianQuietHours(date = new Date()): boolean {
  // Convert date to IST (UTC+5:30)
  const utc = date.getTime() + date.getTimezoneOffset() * 60000;
  const istDate = new Date(utc + 5.5 * 3600000);
  const hours = istDate.getHours();
  // Active if >= 21:00 or < 09:00
  return hours >= 21 || hours < 9;
}

export function MessageDraftEditor({
  draft,
  leadName,
  recipientPhone,
  isSuppressed = false,
  suppressionReason,
  onSaveDraft,
  onApproveAndSend,
  onRegenerateDraft,
  isSaving = false,
  isSending = false,
  isRegenerating = false,
}: MessageDraftEditorProps) {
  const [editedBody, setEditedBody] = useState<string>(
    draft?.message.message_body || ""
  );
  const [instructions, setInstructions] = useState<string>("");
  const [showInstructions, setShowInstructions] = useState<boolean>(false);
  const [isPreviewMode, setIsPreviewMode] = useState<boolean>(false);
  const [ignoreQuietHours, setIgnoreQuietHours] = useState<boolean>(false);
  const [showSendConfirm, setShowSendConfirm] = useState<boolean>(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const [prevBody, setPrevBody] = useState(draft?.message.message_body || "");
  if (draft?.message.message_body && draft.message.message_body !== prevBody) {
    setPrevBody(draft.message.message_body);
    setEditedBody(draft.message.message_body);
  }

  const hasPhone = Boolean(recipientPhone && recipientPhone.trim());
  const inQuietHours = isIndianQuietHours();
  const isDirty = draft ? editedBody !== draft.message.message_body : false;
  const charCount = editedBody.length;
  const maxChars = 2000;

  // Blocked state evaluations per UI-UX.md Section 5.8
  const isOptedOut = isSuppressed;
  const isBlocked = isOptedOut || !hasPhone;

  const handleSave = async (status: MessageStatus = "draft") => {
    setValidationError(null);
    if (!editedBody.trim()) {
      setValidationError("Message text cannot be empty.");
      return;
    }
    await onSaveDraft(editedBody, status);
  };

  const handleSendClick = () => {
    setValidationError(null);
    if (isBlocked) return;
    const trimmed = editedBody.trim();
    if (!trimmed) {
      setValidationError("Message text cannot be empty.");
      return;
    }
    if (!/stop/i.test(trimmed)) {
      setValidationError("Outreach message must contain an opt-out line (e.g. 'Reply STOP to opt out') to prevent recipient complaints.");
      return;
    }
    setShowSendConfirm(true);
  };

  const handleConfirmSend = async () => {
    setShowSendConfirm(false);
    await onApproveAndSend(editedBody.trim(), ignoreQuietHours);
  };

  const handleRegenerate = async () => {
    setValidationError(null);
    await onRegenerateDraft(instructions.trim() || undefined);
    setInstructions("");
    setShowInstructions(false);
  };

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-5">
      {/* Header with Lead & Phone Context */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-border pb-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            WhatsApp outreach draft
          </h3>
          <p className="text-xs text-muted-foreground">
            Recipient:{" "}
            <span className="font-medium text-foreground">{leadName}</span> (
            {formatPhoneDisplay(recipientPhone)})
          </p>
        </div>

        {/* Status chip */}
        <div className="flex items-center gap-2">
          {draft?.status && (
            <span className="rounded-full border border-border bg-muted/40 px-2.5 py-0.5 text-xs font-medium text-muted-foreground capitalize">
              {draft.status.replace("_", " ")}
            </span>
          )}
          <span className="rounded-full border border-good/30 bg-good/10 px-2.5 py-0.5 text-xs font-medium text-good">
            Estimated cost: ₹{draft?.estimated_cost_inr ? draft.estimated_cost_inr.toFixed(2) : "0.00"}
          </span>
        </div>
      </div>

      {/* Blocked state alert banners per UI-UX.md Section 5.8 */}
      {isOptedOut && (
        <div className="flex items-start gap-2 rounded-md border border-problem/40 bg-problem/10 p-3 text-xs text-problem">
          <ShieldAlert className="mt-0.5 size-4 shrink-0" />
          <div>
            <span className="font-medium">Outreach blocked: </span>
            This number opted out of communications
            {suppressionReason ? ` (${suppressionReason})` : ""}. It cannot be messaged.
          </div>
        </div>
      )}

      {!hasPhone && !isOptedOut && (
        <div className="flex items-start gap-2 rounded-md border border-caution/40 bg-caution/10 p-3 text-xs text-caution">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <div>
            <span className="font-medium">No phone listed: </span>
            This lead does not have a phone number. A phone number is required to send via WhatsApp.
          </div>
        </div>
      )}

      {inQuietHours && !isBlocked && (
        <div className="flex items-start gap-2 rounded-md border border-caution/40 bg-caution/10 p-3 text-xs text-caution">
          <Moon className="mt-0.5 size-4 shrink-0" />
          <div className="flex-1">
            <span className="font-medium">Indian quiet hours active (21:00 to 09:00 IST): </span>
            To protect WhatsApp account reputation, messages are normally held until 9:00 am.
            <div className="mt-2 flex items-center gap-2">
              <label className="flex items-center gap-1.5 cursor-pointer font-normal text-foreground">
                <input
                  type="checkbox"
                  checked={ignoreQuietHours}
                  onChange={(e) => setIgnoreQuietHours(e.target.checked)}
                  className="rounded border-border text-primary focus:ring-primary"
                />
                <span>Send immediately (override quiet hours safeguard)</span>
              </label>
            </div>
          </div>
        </div>
      )}

      {validationError && (
        <div className="rounded-md border border-problem/40 bg-problem/10 p-3 text-xs text-problem">
          {validationError}
        </div>
      )}

      {/* Cited Evidence Strip */}
      {draft?.evidence_cited && draft.evidence_cited.length > 0 && (
        <div className="rounded-md border border-border bg-muted/20 p-2.5">
          <div className="text-xs font-medium text-foreground mb-1.5">
            Verified findings cited in this draft:
          </div>
          <div className="flex flex-wrap gap-1.5">
            {draft.evidence_cited.map((item, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1 rounded border border-primary/30 bg-primary/10 px-2 py-0.5 text-xs text-primary"
              >
                <CheckCircle2 className="size-3" />
                {item}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Editor & Preview Toggle */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsPreviewMode(false)}
            className={`inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              !isPreviewMode
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Edit3 className="size-3.5" />
            Edit message
          </button>
          <button
            type="button"
            onClick={() => setIsPreviewMode(true)}
            className={`inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              isPreviewMode
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Eye className="size-3.5" />
            Recipient preview
          </button>
        </div>

        <span className="text-xs text-muted-foreground tabular-nums">
          {charCount} / {maxChars} characters
        </span>
      </div>

      {/* Editor Area or Preview Bubble */}
      {!isPreviewMode ? (
        <div className="space-y-2">
          <Textarea
            value={editedBody}
            onChange={(e) => setEditedBody(e.target.value)}
            disabled={isBlocked || isSending || isSaving || isRegenerating}
            rows={7}
            placeholder="Review and customize message draft..."
            className="font-sans text-sm resize-y leading-relaxed border-border focus-visible:ring-primary"
          />
          <p className="text-xs text-muted-foreground">
            Must include an opt-out line (e.g. &quot;Reply STOP to opt out&quot;).
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-line bg-surface p-4">
          <div className="text-xs font-medium text-muted-foreground mb-2">
            Message preview as delivered to prospect:
          </div>
          <div className="max-w-md rounded-2xl rounded-tl-sm border border-border bg-petrol-soft p-3.5 text-sm leading-relaxed text-ink shadow-none whitespace-pre-wrap">
            {editedBody || (
              <span className="italic text-muted-foreground">Draft is empty</span>
            )}
          </div>
        </div>
      )}

      {/* Optional Custom Instructions Panel for Regeneration */}
      {showInstructions && (
        <div className="rounded-md border border-border bg-muted/20 p-3 space-y-2">
          <label className="text-xs font-medium text-foreground block">
            Instructions for AI rewrite (tone, specific angle, offer):
          </label>
          <input
            type="text"
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder="e.g. Emphasize mobile load speed; keep it under 3 sentences."
            className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      )}

      {/* Action Bar */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between pt-2 border-t border-border">
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setShowInstructions((prev) => !prev)}
            disabled={isBlocked || isRegenerating || isSending}
            className="text-xs"
          >
            <RotateCw
              className={`mr-1.5 size-3.5 ${isRegenerating ? "animate-spin" : ""}`}
            />
            {showInstructions ? "Hide instructions" : "Regenerate options"}
          </Button>

          {showInstructions && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleRegenerate}
              disabled={isBlocked || isRegenerating || isSending}
              className="text-xs"
            >
              Run rewrite
            </Button>
          )}

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => handleSave("draft")}
            disabled={!isDirty || isBlocked || isSaving || isSending}
            className="text-xs"
          >
            <Save className="mr-1.5 size-3.5" />
            {isSaving ? "Saving..." : "Save draft"}
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="default"
            size="sm"
            onClick={handleSendClick}
            disabled={isBlocked || isSending || isRegenerating || !editedBody.trim()}
            className="bg-primary text-primary-foreground hover:bg-primary/90 text-xs"
          >
            <Send className="mr-1.5 size-3.5" />
            {isSending ? "Dispatching..." : "Approve and send"}
          </Button>
        </div>
      </div>

      {/* Confirmation Dialog before sending */}
      {showSendConfirm && (
        <div className="rounded-lg border border-primary/40 bg-primary/10 p-4 space-y-3">
          <div className="text-xs font-semibold text-foreground">
            Confirm message dispatch
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            You are about to send this WhatsApp message to{" "}
            <span className="font-medium text-foreground">{leadName}</span> at{" "}
            <span className="font-medium text-foreground">
              {formatPhoneDisplay(recipientPhone)}
            </span>
            . Explicit human approval will be logged.
          </p>
          {inQuietHours && ignoreQuietHours && (
            <p className="text-xs text-caution font-medium">
              Note: Sending during Indian quiet hours under manual override.
            </p>
          )}
          <div className="flex items-center justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setShowSendConfirm(false)}
              disabled={isSending}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="default"
              size="sm"
              onClick={handleConfirmSend}
              disabled={isSending}
              className="text-xs bg-primary text-primary-foreground"
            >
              {isSending ? "Sending..." : "Confirm & send now"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

