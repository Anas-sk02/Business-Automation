"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { UserProfile, UpdateProfileInput } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, Check, Plus, X, RefreshCw } from "lucide-react";

export function ProfileSettings() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [fullName, setFullName] = useState<string>("");
  const [companyName, setCompanyName] = useState<string>("");
  const [whatsappNumber, setWhatsappNumber] = useState<string>("");
  const [serviceDescriptions, setServiceDescriptions] = useState<string[]>([]);
  const [newServiceInput, setNewServiceInput] = useState<string>("");
  const [timezone, setTimezone] = useState<string>("Asia/Kolkata");

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  async function loadProfile() {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.get<{ data: UserProfile }>("/api/auth/me");
      if (res?.data) {
        setProfile(res.data);
        setFullName(res.data.full_name || "");
        setCompanyName(res.data.company_name || "");
        setWhatsappNumber(res.data.whatsapp_number || "");
        setServiceDescriptions(Array.isArray(res.data.service_descriptions) ? res.data.service_descriptions : []);
        setTimezone(res.data.timezone || "Asia/Kolkata");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load profile details";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadProfile();
  }, []);

  function handleAddService(e?: React.FormEvent) {
    if (e) e.preventDefault();
    const trimmed = newServiceInput.trim();
    if (!trimmed) return;
    if (serviceDescriptions.some((s) => s.toLowerCase() === trimmed.toLowerCase())) {
      setNewServiceInput("");
      return;
    }
    setServiceDescriptions([...serviceDescriptions, trimmed]);
    setNewServiceInput("");
  }

  function handleRemoveService(indexToRemove: number) {
    setServiceDescriptions(serviceDescriptions.filter((_, idx) => idx !== indexToRemove));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    setSuccessMessage(null);

    // Validate WhatsApp number if present
    if (whatsappNumber.trim()) {
      const cleanPhone = whatsappNumber.trim().replace(/\s+/g, "").replace(/-/g, "");
      const e164Regex = /^\+[1-9]\d{9,14}$/;
      if (!e164Regex.test(cleanPhone)) {
        setError("WhatsApp number must include country code in valid E.164 format (e.g. +91 98220 12345)");
        setIsSaving(false);
        return;
      }
    }

    const payload: UpdateProfileInput = {
      full_name: fullName.trim(),
      company_name: companyName.trim(),
      whatsapp_number: whatsappNumber.trim(),
      service_descriptions: serviceDescriptions,
      timezone: timezone.trim() || "Asia/Kolkata",
    };

    try {
      const res = await api.put<{ data: UserProfile }>("/api/auth/profile", payload);
      if (res?.data) {
        setProfile(res.data);
        setFullName(res.data.full_name || "");
        setCompanyName(res.data.company_name || "");
        setWhatsappNumber(res.data.whatsapp_number || "");
        setServiceDescriptions(Array.isArray(res.data.service_descriptions) ? res.data.service_descriptions : []);
      }
      setSuccessMessage("Profile updated successfully");
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update profile";
      setError(msg);
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return (
      <Card className="border border-border">
        <CardHeader>
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-64 mt-1" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border border-border">
      <CardHeader className="pb-4">
        <CardTitle className="text-base font-semibold text-foreground">
          Profile Details
        </CardTitle>
        <CardDescription className="text-xs text-muted-foreground mt-0.5">
          Your organization identity used for personalized outreach messages
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="mb-4 p-3 rounded-md border border-problem/30 bg-problem-soft text-problem flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
            <Button variant="ghost" size="sm" onClick={loadProfile} className="h-7 px-2 text-xs">
              <RefreshCw className="w-3 h-3 mr-1" />
              Retry
            </Button>
          </div>
        )}

        {successMessage && (
          <div className="mb-4 p-3 rounded-md border border-good/30 bg-good-soft text-good flex items-center gap-2 text-xs">
            <Check className="w-4 h-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Email (Read-only) */}
            <div className="space-y-1.5">
              <Label className="text-xs font-medium text-muted-foreground">Account email</Label>
              <Input
                type="email"
                value={profile?.email || ""}
                disabled
                className="bg-muted text-muted-foreground cursor-not-allowed h-9 text-xs"
              />
              <p className="text-[11px] text-muted-foreground">
                Managed by authentication provider
              </p>
            </div>

            {/* Timezone */}
            <div className="space-y-1.5">
              <Label htmlFor="timezone" className="text-xs font-medium text-foreground">
                Operational timezone
              </Label>
              <Input
                id="timezone"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                placeholder="Asia/Kolkata"
                className="h-9 text-xs"
              />
              <p className="text-[11px] text-muted-foreground">
                Used to enforce Indian quiet hours (21:00 to 09:00 IST)
              </p>
            </div>

            {/* Full Name */}
            <div className="space-y-1.5">
              <Label htmlFor="full_name" className="text-xs font-medium text-foreground">
                Your full name
              </Label>
              <Input
                id="full_name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. John Doe"
                className="h-9 text-xs"
                maxLength={100}
              />
            </div>

            {/* Company Name */}
            <div className="space-y-1.5">
              <Label htmlFor="company_name" className="text-xs font-medium text-foreground">
                Company name
              </Label>
              <Input
                id="company_name"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g. Apex Digital Solutions"
                className="h-9 text-xs"
                maxLength={100}
              />
            </div>
          </div>

          {/* WhatsApp Outreach Number */}
          <div className="space-y-1.5">
            <Label htmlFor="whatsapp_number" className="text-xs font-medium text-foreground">
              WhatsApp sender number
            </Label>
            <Input
              id="whatsapp_number"
              value={whatsappNumber}
              onChange={(e) => setWhatsappNumber(e.target.value)}
              placeholder="+91 98220 12345"
              className="h-9 text-xs max-w-sm"
              maxLength={20}
            />
            <p className="text-[11px] text-muted-foreground">
              Number linked to WAHA or Twilio sender. Use E.164 format with country code.
            </p>
          </div>

          {/* Service Descriptions Tag List */}
          <div className="space-y-2 pt-2 border-t border-border">
            <div>
              <Label className="text-xs font-medium text-foreground">
                Services offered
              </Label>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Included in AI personalized outreach pitches and solution proposals
              </p>
            </div>

            {/* Tag List */}
            <div className="flex flex-wrap items-center gap-1.5 min-h-[32px]">
              {serviceDescriptions.map((service, index) => (
                <span
                  key={`${service}-${index}`}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-muted text-foreground border border-border"
                >
                  <span>{service}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveService(index)}
                    className="text-muted-foreground hover:text-foreground transition-colors"
                    aria-label={`Remove ${service}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
              {serviceDescriptions.length === 0 && (
                <span className="text-xs text-muted-foreground italic">
                  No services added yet. Add services you provide to prospective clients.
                </span>
              )}
            </div>

            {/* Add Service Tag Input */}
            <div className="flex items-center gap-2 max-w-sm pt-1">
              <Input
                value={newServiceInput}
                onChange={(e) => setNewServiceInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddService();
                  }
                }}
                placeholder="e.g. Website Redesign, SEO"
                className="h-8 text-xs"
                maxLength={50}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => handleAddService()}
                className="h-8 px-2.5 text-xs shrink-0"
              >
                <Plus className="w-3.5 h-3.5 mr-1" />
                Add
              </Button>
            </div>
          </div>

          {/* Action Row */}
          <div className="pt-4 border-t border-border flex items-center justify-end">
            <Button type="submit" disabled={isSaving} size="sm" className="h-9 px-4">
              {isSaving ? "Saving changes..." : "Save profile"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

