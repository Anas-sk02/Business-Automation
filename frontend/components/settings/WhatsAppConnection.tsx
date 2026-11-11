"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import type { WhatsAppSessionStatus, WhatsAppSessionQRResponse, ResponseEnvelope } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Smartphone,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  QrCode,
  LogOut,
  Loader2,
  ShieldCheck,
} from "lucide-react";

export function WhatsAppConnection() {
  const [session, setSession] = useState<WhatsAppSessionStatus | null>(null);
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isStarting, setIsStarting] = useState<boolean>(false);
  const [isDisconnecting, setIsDisconnecting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const res = await api.get<ResponseEnvelope<WhatsAppSessionStatus>>("/api/whatsapp/session/status");
      const data = res?.data || (res as unknown as WhatsAppSessionStatus);
      if (data) {
        setSession(data);
        if (data.connected) {
          setQrCode(null);
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load WhatsApp session status";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadQR = useCallback(async () => {
    try {
      const res = await api.get<ResponseEnvelope<WhatsAppSessionQRResponse>>("/api/whatsapp/session/qr");
      const data = res?.data || (res as unknown as WhatsAppSessionQRResponse);
      if (data?.qr_code) {
        setQrCode(data.qr_code);
      }
    } catch {
      // Non-blocking
    }
  }, []);

  const handleStartSession = async () => {
    setIsStarting(true);
    setError(null);
    try {
      const res = await api.post<ResponseEnvelope<WhatsAppSessionStatus>>("/api/whatsapp/session/start");
      const data = res?.data || (res as unknown as WhatsAppSessionStatus);
      if (data) {
        setSession(data);
      }
      // Fetch QR immediately
      await loadQR();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to start WhatsApp connection";
      setError(msg);
    } finally {
      setIsStarting(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm("Are you sure you want to disconnect your WhatsApp account from this workspace?")) {
      return;
    }

    setIsDisconnecting(true);
    setError(null);
    try {
      await api.post("/api/whatsapp/session/logout");
      setSession(null);
      setQrCode(null);
      await loadStatus();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to disconnect WhatsApp";
      setError(msg);
    } finally {
      setIsDisconnecting(false);
    }
  };

  // Initial load
  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // Polling when scanning QR code or starting
  useEffect(() => {
    if (session && !session.connected && (session.status === "SCAN_QR_CODE" || session.status === "STARTING" || qrCode)) {
      pollIntervalRef.current = setInterval(async () => {
        try {
          const res = await api.get<ResponseEnvelope<WhatsAppSessionStatus>>("/api/whatsapp/session/status");
          const data = res?.data || (res as unknown as WhatsAppSessionStatus);
          if (data) {
            setSession(data);
            if (data.connected) {
              setQrCode(null);
              if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
            }
          }
        } catch {
          // Keep polling
        }
      }, 3000);
    } else {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [session, qrCode]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-72" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    );
  }

  const isConnected = session?.connected === true;
  const isOffline = session?.status === "SERVICE_UNAVAILABLE";

  return (
    <div className="space-y-6">
      <Card className="border border-border">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <Smartphone className="h-5 w-5 text-primary" />
                <span>WhatsApp Outreach Connection</span>
              </CardTitle>
              <CardDescription>
                Connect your individual WhatsApp account. Outreach messages and incoming replies are strictly routed through your own paired phone.
              </CardDescription>
            </div>

            {isConnected ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                Connected
              </span>
            ) : isOffline ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                Bridge Offline
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-muted text-muted-foreground border border-border">
                Not Connected
              </span>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          {error && (
            <div className="p-3 text-sm rounded-md bg-destructive/10 text-destructive border border-destructive/20 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Connected State */}
          {isConnected && (
            <div className="rounded-lg border border-border bg-card p-5 space-y-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center font-bold">
                    <CheckCircle2 className="h-6 w-6" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">
                      {session?.push_name || "Paired WhatsApp Account"}
                    </h3>
                    <p className="text-xs text-muted-foreground font-mono mt-0.5">
                      {session?.phone_number ? `+${session.phone_number}` : "Phone connected"}
                    </p>
                  </div>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDisconnect}
                  disabled={isDisconnecting}
                  className="text-destructive hover:bg-destructive/10 hover:text-destructive border-border"
                >
                  {isDisconnecting ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                      Disconnecting...
                    </>
                  ) : (
                    <>
                      <LogOut className="h-3.5 w-3.5 mr-1.5" />
                      Disconnect
                    </>
                  )}
                </Button>
              </div>

              <div className="pt-2 border-t border-border/60 flex items-center gap-2 text-xs text-muted-foreground">
                <ShieldCheck className="h-4 w-4 text-primary shrink-0" />
                <span>
                  Tenant session <code className="bg-muted px-1.5 py-0.5 rounded text-[11px]">{session?.session_name}</code> is active. Your outreach is fully isolated from other users.
                </span>
              </div>
            </div>
          )}

          {/* QR Pairing State */}
          {!isConnected && !isOffline && (
            <div className="space-y-6">
              {qrCode ? (
                <div className="flex flex-col sm:flex-row items-center gap-6 p-6 rounded-lg border border-border bg-muted/20">
                  {/* QR Image Box */}
                  <div className="p-3 bg-white rounded-xl shadow-sm border border-border/80 shrink-0">
                    <img
                      src={qrCode}
                      alt="Scan WhatsApp QR Code"
                      className="w-56 h-56 object-contain"
                    />
                  </div>

                  {/* Pairing instructions */}
                  <div className="space-y-3">
                    <div className="inline-flex items-center gap-2 text-xs font-semibold text-primary">
                      <QrCode className="h-4 w-4" />
                      <span>Scan QR Code to Link Device</span>
                    </div>

                    <ol className="text-xs text-muted-foreground space-y-2 list-decimal list-inside leading-relaxed">
                      <li>Open <strong>WhatsApp</strong> on your mobile phone</li>
                      <li>Tap <strong>Settings</strong> or <strong>Menu (⋮)</strong></li>
                      <li>Select <strong>Linked Devices</strong> and tap <strong>Link a Device</strong></li>
                      <li>Point your phone camera at the QR code on this screen</li>
                    </ol>

                    <div className="pt-2 flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={loadQR}
                        className="text-xs"
                      >
                        <RefreshCw className="h-3 w-3 mr-1" />
                        Refresh QR
                      </Button>
                      <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                        <Loader2 className="h-3 w-3 animate-spin text-primary" />
                        Waiting for scan...
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 px-4 rounded-lg border border-dashed border-border space-y-4">
                  <div className="mx-auto w-12 h-12 rounded-full bg-primary/10 text-primary flex items-center justify-center">
                    <Smartphone className="h-6 w-6" />
                  </div>
                  <div className="space-y-1 max-w-md mx-auto">
                    <h3 className="text-sm font-semibold text-foreground">
                      No WhatsApp account currently linked
                    </h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Link your phone via WhatsApp Web to start sending approved outreach messages and receiving client replies directly to your own number.
                    </p>
                  </div>
                  <div>
                    <Button
                      onClick={handleStartSession}
                      disabled={isStarting}
                      className="text-xs font-medium"
                    >
                      {isStarting ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin mr-2" />
                          Generating QR Code...
                        </>
                      ) : (
                        <>
                          <QrCode className="h-3.5 w-3.5 mr-2" />
                          Connect My WhatsApp
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Bridge Offline State */}
          {isOffline && (
            <div className="p-4 rounded-lg border border-amber-500/20 bg-amber-500/5 text-xs text-muted-foreground space-y-2">
              <p className="font-medium text-foreground flex items-center gap-1.5">
                <AlertCircle className="h-4 w-4 text-amber-500 shrink-0" />
                WhatsApp Bridge Service Offline
              </p>
              <p className="leading-relaxed">
                The local or cloud WAHA Docker service is currently unreachable on port 3001. Please make sure WAHA is started to link or manage your WhatsApp session.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={loadStatus}
                className="mt-2 text-xs"
              >
                <RefreshCw className="h-3 w-3 mr-1.5" />
                Retry Connection Check
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

