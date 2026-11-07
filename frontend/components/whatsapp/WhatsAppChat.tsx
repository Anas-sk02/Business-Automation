"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import type {
  WhatsAppMessage,
  WhatsAppDraftResponse,
  ReplyClassification,
  MessageStatus,
} from "@/types";
import { api, ApiClientError } from "@/lib/api";
import { MessageDraftEditor } from "./MessageDraftEditor";
import { Button } from "@/components/ui/button";
import {
  Smartphone,
  Check,
  CheckCheck,
  AlertCircle,
  RotateCw,
  ShieldAlert,
  Info,
} from "lucide-react";

interface WhatsAppChatProps {
  leadId: string;
  leadName: string;
  recipientPhone?: string | null;
  isSuppressed?: boolean;
  suppressionReason?: string | null;
  pipelineStage?: string;
  onStageChange?: (newStage: string) => void;
}

/**
 * Calculates whether the lead is within the 24-hour customer service window
 * based on the most recent inbound message.
 */
export function get24HourWindowStatus(messages: WhatsAppMessage[]): {
  isOpen: boolean;
  closesAt?: Date | null;
  formattedClosingTime?: string;
} {
  const inboundMessages = messages
    .filter((m) => m.direction === "inbound" && m.created_at)
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

  if (inboundMessages.length === 0) {
    return { isOpen: false, closesAt: null };
  }

  const lastInboundTime = new Date(inboundMessages[0].created_at).getTime();
  const windowClosesTime = lastInboundTime + 24 * 60 * 60 * 1000;
  const now = Date.now();

  if (now < windowClosesTime) {
    const closesAt = new Date(windowClosesTime);
    const formatted = closesAt.toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
    return {
      isOpen: true,
      closesAt,
      formattedClosingTime: formatted,
    };
  }

  return { isOpen: false, closesAt: null };
}

/**
 * Format timestamp to friendly time string (e.g. '4:10 pm').
 */
export function formatMessageTime(isoString?: string | null): string {
  if (!isoString) return "";
  try {
    const dt = new Date(isoString);
    if (isNaN(dt.getTime())) return "";
    return dt.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

/**
 * Map reply classifications to readable badges and visual tones.
 */
export function getClassificationChip(classification?: ReplyClassification | null) {
  if (!classification) return null;

  switch (classification) {
    case "interested":
    case "meeting_request":
    case "pricing_request":
    case "wants_info":
      return {
        label:
          classification === "meeting_request"
            ? "Meeting requested"
            : classification === "pricing_request"
            ? "Pricing requested"
            : classification === "wants_info"
            ? "Requested details"
            : "Interested",
        badgeClass: "border-good/40 bg-good/10 text-good",
      };
    case "not_interested":
    case "wrong_number":
      return {
        label:
          classification === "wrong_number" ? "Wrong number" : "Not interested",
        badgeClass: "border-border bg-muted/40 text-muted-foreground",
      };
    case "opt_out":
      return {
        label: "Opt-out requested",
        badgeClass: "border-problem/40 bg-problem/10 text-problem",
      };
    case "not_now":
    case "unclear":
    default:
      return {
        label: classification === "not_now" ? "Not now" : "Unclear",
        badgeClass: "border-caution/40 bg-caution/10 text-caution",
      };
  }
}

export function WhatsAppChat({
  leadId,
  leadName,
  recipientPhone,
  isSuppressed = false,
  suppressionReason,
  pipelineStage,
  onStageChange,
}: WhatsAppChatProps) {
  const [messages, setMessages] = useState<WhatsAppMessage[]>([]);
  const [draft, setDraft] = useState<WhatsAppDraftResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isGeneratingDraft, setIsGeneratingDraft] = useState<boolean>(false);
  const [isSavingDraft, setIsSavingDraft] = useState<boolean>(false);
  const [isSendingMessage, setIsSendingMessage] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Fetch timeline messages
  const fetchMessages = useCallback(async () => {
    try {
      const response = await api.get<{ data: WhatsAppMessage[] }>(
        `/api/leads/${leadId}/whatsapp/messages`
      );
      setMessages(response.data || []);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError("Failed to load WhatsApp conversation history.");
      }
    }
  }, [leadId]);

  // Fetch active draft
  const fetchDraft = useCallback(async () => {
    try {
      const response = await api.get<{ data: WhatsAppDraftResponse }>(
        `/api/leads/${leadId}/whatsapp/draft`
      );
      setDraft(response.data || null);
    } catch (err: unknown) {
      // 404 indicates no active draft exists yet
      if (err instanceof ApiClientError && err.status === 404) {
        setDraft(null);
      } else if (err instanceof ApiClientError) {
        setError(err.message);
      }
    }
  }, [leadId]);

  useEffect(() => {
    let ignore = false;
    async function init() {
      try {
        const [msgRes, draftRes] = await Promise.allSettled([
          api.get<{ data: WhatsAppMessage[] }>(`/api/leads/${leadId}/whatsapp/messages`),
          api.get<{ data: WhatsAppDraftResponse }>(`/api/leads/${leadId}/whatsapp/draft`),
        ]);

        if (ignore) return;

        if (msgRes.status === "fulfilled" && msgRes.value?.data) {
          setMessages(msgRes.value.data);
        } else {
          setMessages([]);
        }

        if (draftRes.status === "fulfilled" && draftRes.value?.data) {
          setDraft(draftRes.value.data);
        } else {
          setDraft(null);
        }
        setError(null);
      } catch (err: unknown) {
        if (!ignore) {
          if (err instanceof ApiClientError) {
            setError(err.message);
          } else {
            setError("Failed to load WhatsApp conversation.");
          }
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
  }, [leadId]);

  useEffect(() => {
    if (!isLoading && messages.length > 0) {
      scrollToBottom();
    }
  }, [isLoading, messages.length]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    setError(null);
    setFeedback(null);
    await Promise.all([fetchMessages(), fetchDraft()]);
    setIsRefreshing(false);
  };

  // Draft operations
  const handleGenerateDraft = async (instructions?: string) => {
    setIsGeneratingDraft(true);
    setError(null);
    setFeedback(null);
    try {
      const response = await api.post<{
        data: WhatsAppDraftResponse;
        message: string;
      }>(`/api/leads/${leadId}/whatsapp/draft`, { instructions });
      setDraft(response.data);
      setFeedback("Outreach draft generated successfully.");
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError("Failed to generate outreach draft.");
      }
    } finally {
      setIsGeneratingDraft(false);
    }
  };

  const handleSaveDraft = async (
    messageBody: string,
    status: MessageStatus = "draft"
  ) => {
    setIsSavingDraft(true);
    setError(null);
    setFeedback(null);
    try {
      const response = await api.put<{
        data: WhatsAppDraftResponse;
        message: string;
      }>(`/api/leads/${leadId}/whatsapp/draft`, {
        message_body: messageBody,
        status,
      });
      setDraft(response.data);
      setFeedback("Draft saved.");
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError("Failed to save draft changes.");
      }
    } finally {
      setIsSavingDraft(false);
    }
  };

  const handleApproveAndSend = async (
    currentBody?: string,
    ignoreQuietHours = false
  ) => {
    setIsSendingMessage(true);
    setError(null);
    setFeedback(null);
    try {
      const bodyToSend = (currentBody || draft?.message.message_body || "").trim();
      if (!bodyToSend) {
        setError("Cannot send an empty message.");
        setIsSendingMessage(false);
        return;
      }

      // Step 1: Ensure draft is updated with latest edits and approved
      await api.put(`/api/leads/${leadId}/whatsapp/draft`, {
        message_body: bodyToSend,
        status: "approved",
      });

      // Step 2: Dispatch message
      await api.post(`/api/leads/${leadId}/whatsapp/send`, {
        ignore_quiet_hours: ignoreQuietHours,
      });

      setFeedback("Message dispatched successfully via WhatsApp.");
      setDraft(null);
      if (onStageChange && pipelineStage !== "contacted") {
        onStageChange("contacted");
      }
      await fetchMessages();
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError("Failed to dispatch WhatsApp message.");
      }
    } finally {
      setIsSendingMessage(false);
    }
  };

  const windowStatus = get24HourWindowStatus(messages);

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center space-y-3">
        <RotateCw className="mx-auto size-6 animate-spin text-muted-foreground" />
        <p className="text-xs text-muted-foreground">
          Loading conversation thread and draft...
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Thread Controls Header */}
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <Smartphone className="size-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">
            WhatsApp conversation thread
          </h3>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="text-xs h-7"
        >
          <RotateCw
            className={`mr-1.5 size-3.5 ${isRefreshing ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      </div>

      {/* Alerts & Feedback */}
      {feedback && (
        <div className="rounded-md border border-good/40 bg-good/10 p-3 text-xs text-good flex items-center gap-2">
          <Check className="size-4 shrink-0" />
          <span>{feedback}</span>
        </div>
      )}

      {error && (
        <div className="rounded-md border border-problem/40 bg-problem/10 p-3 text-xs text-problem flex items-center gap-2">
          <AlertCircle className="size-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 24-Hour Service Window Banner per UI-UX.md Section 6.7 */}
      {windowStatus.isOpen ? (
        <div className="flex items-center gap-2 rounded-md border border-good/40 bg-good/10 p-3 text-xs text-good">
          <Info className="size-4 shrink-0" />
          <span>
            24-hour service window active: You can send free-form replies until{" "}
            {windowStatus.formattedClosingTime || "today"}.
          </span>
        </div>
      ) : messages.length > 0 ? (
        <div className="flex items-center gap-2 rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
          <Info className="size-4 shrink-0" />
          <span>
            The 24-hour service window has closed. Outbound messages use evidence-grounded templates.
          </span>
        </div>
      ) : null}

      {/* Chronological Chat Messages Display */}
      <div className="rounded-lg border border-border bg-muted/10 p-4 min-h-[220px] max-h-[460px] overflow-y-auto space-y-3">
        {messages.length === 0 ? (
          <div className="py-12 text-center space-y-2">
            <Smartphone className="mx-auto size-8 text-muted-foreground/60" />
            <p className="text-sm font-medium text-foreground">
              No WhatsApp messages sent yet
            </p>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto">
              Generate a personalized, evidence-grounded outreach draft below to begin communication.
            </p>
          </div>
        ) : (
          messages.map((msg) => {
            const isOutbound = msg.direction === "outbound";
            const timeStr = formatMessageTime(msg.created_at);
            const classificationChip = getClassificationChip(
              msg.reply_classification
            );
            const isLowConfidence =
              msg.classification_confidence !== null &&
              msg.classification_confidence !== undefined &&
              msg.classification_confidence < 0.6;

            return (
              <div
                key={msg.id}
                className={`flex flex-col ${
                  isOutbound ? "items-end" : "items-start"
                }`}
              >
                {/* Bubble Container */}
                <div
                  className={`max-w-[85%] rounded-2xl p-3.5 text-sm leading-relaxed ${
                    isOutbound
                      ? "rounded-tr-sm bg-primary/10 border border-primary/20 text-foreground"
                      : "rounded-tl-sm bg-card border border-border text-foreground"
                  }`}
                >
                  {/* Classification badge for Inbound */}
                  {!isOutbound && classificationChip && (
                    <div className="mb-2 flex items-center gap-1.5 flex-wrap">
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${classificationChip.badgeClass}`}
                      >
                        {classificationChip.label}
                      </span>
                      {isLowConfidence && (
                        <span className="rounded-full border border-caution/40 bg-caution/10 px-2 py-0.5 text-[11px] text-caution">
                          Needs your review
                        </span>
                      )}
                    </div>
                  )}

                  {/* Message Body */}
                  <div className="whitespace-pre-wrap">{msg.message_body}</div>
                </div>

                {/* Subtext with status and timestamp */}
                <div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground px-1">
                  {isOutbound ? (
                    <>
                      <span>{timeStr}</span>
                      <span>·</span>
                      <span className="capitalize font-medium">
                        {msg.status === "delivered" ? (
                          <span className="inline-flex items-center gap-0.5 text-good">
                            <CheckCheck className="size-3" /> Delivered
                          </span>
                        ) : msg.status === "read" ? (
                          <span className="inline-flex items-center gap-0.5 text-primary">
                            <CheckCheck className="size-3" /> Read
                          </span>
                        ) : msg.status === "sent" ? (
                          <span className="inline-flex items-center gap-0.5">
                            <Check className="size-3" /> Sent
                          </span>
                        ) : msg.status === "failed" ? (
                          <span className="inline-flex items-center gap-0.5 text-problem font-medium">
                            <AlertCircle className="size-3" /> Delivery failed
                            {msg.error_message ? `: ${msg.error_message}` : ""}
                          </span>
                        ) : (
                          msg.status.replace("_", " ")
                        )}
                      </span>
                    </>
                  ) : (
                    <>
                      <span>Received {timeStr}</span>
                    </>
                  )}
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suppression Notification per UI-UX.md Section 6.7 */}
      {isSuppressed ? (
        <div className="rounded-lg border border-problem/40 bg-problem/10 p-4 text-xs text-problem flex items-start gap-2.5">
          <ShieldAlert className="mt-0.5 size-4 shrink-0" />
          <div>
            <div className="font-semibold">Recipient has opted out</div>
            <p className="mt-0.5 text-muted-foreground leading-relaxed">
              This prospect opted out of communications
              {suppressionReason ? ` (${suppressionReason})` : ""}. All automated
              follow-ups have been cancelled and no further messages can be sent.
            </p>
          </div>
        </div>
      ) : draft ? (
        /* Active Draft Editor */
        <MessageDraftEditor
          draft={draft}
          leadId={leadId}
          leadName={leadName}
          recipientPhone={recipientPhone}
          isSuppressed={isSuppressed}
          suppressionReason={suppressionReason}
          onSaveDraft={handleSaveDraft}
          onApproveAndSend={handleApproveAndSend}
          onRegenerateDraft={handleGenerateDraft}
          isSaving={isSavingDraft}
          isSending={isSendingMessage}
          isRegenerating={isGeneratingDraft}
        />
      ) : (
        /* Empty Draft State: Action to Generate */
        <div className="rounded-lg border border-dashed border-border bg-card p-6 text-center space-y-3">
          <p className="text-xs text-muted-foreground">
            No active message draft for this lead.
          </p>
          <Button
            type="button"
            variant="default"
            size="sm"
            onClick={() => handleGenerateDraft()}
            disabled={isGeneratingDraft || !recipientPhone}
            className="text-xs bg-primary text-primary-foreground"
          >
            <RotateCw
              className={`mr-1.5 size-3.5 ${
                isGeneratingDraft ? "animate-spin" : ""
              }`}
            />
            {isGeneratingDraft ? "Drafting with AI..." : "Generate outreach draft"}
          </Button>
          {!recipientPhone && (
            <p className="text-[11px] text-caution">
              No phone number listed on this lead. Add a phone number to enable outreach.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

