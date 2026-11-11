"use client";

import { useState } from "react";
import { ProfileSettings } from "@/components/settings/ProfileSettings";
import { WhatsAppConnection } from "@/components/settings/WhatsAppConnection";
import { SuppressionTable } from "@/components/settings/SuppressionTable";
import { User, Smartphone, ShieldAlert } from "lucide-react";

type SettingsTab = "profile" | "whatsapp" | "suppression";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("profile");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Settings
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Manage your organization profile, connect your WhatsApp device, and view safeguards
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-border">
        <button
          onClick={() => setActiveTab("profile")}
          className={`flex items-center gap-2 pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "profile"
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
          aria-selected={activeTab === "profile"}
          role="tab"
        >
          <User className="w-4 h-4" />
          <span>Profile</span>
        </button>

        <button
          onClick={() => setActiveTab("whatsapp")}
          className={`flex items-center gap-2 pb-3 px-1 ml-6 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "whatsapp"
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
          aria-selected={activeTab === "whatsapp"}
          role="tab"
        >
          <Smartphone className="w-4 h-4" />
          <span>WhatsApp Connection</span>
        </button>

        <button
          onClick={() => setActiveTab("suppression")}
          className={`flex items-center gap-2 pb-3 px-1 ml-6 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "suppression"
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
          aria-selected={activeTab === "suppression"}
          role="tab"
        >
          <ShieldAlert className="w-4 h-4" />
          <span>Suppression safeguards</span>
        </button>
      </div>

      {/* Tab Content */}
      <div className="pt-2">
        {activeTab === "profile" && <ProfileSettings />}
        {activeTab === "whatsapp" && <WhatsAppConnection />}
        {activeTab === "suppression" && <SuppressionTable />}
      </div>
    </div>
  );
}

