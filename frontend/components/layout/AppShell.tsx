"use client";

import { useState, useEffect } from "react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { api } from "@/lib/api";
import { createClient } from "@/lib/supabase";
import type { UserProfile, ResponseEnvelope } from "@/types";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isTabletCollapsed, setIsTabletCollapsed] = useState(false);

  // Fetch authenticated user profile with graceful fallback
  useEffect(() => {
    let isMounted = true;

    async function loadProfile() {
      const supabase = createClient();
      try {
        // Initial fast populate from local session to prevent UI flash
        const { data: userData } = await supabase.auth.getUser();
        if (isMounted && userData?.user) {
          setUserProfile({
            id: userData.user.id,
            email: userData.user.email || "",
            full_name: (userData.user.user_metadata?.full_name as string) || null,
            company_name: null,
            whatsapp_number: null,
            service_descriptions: [],
            pricing_info: {},
            timezone: "UTC",
            created_at: userData.user.created_at,
            updated_at: userData.user.created_at,
          });
        }

        // Sync full profile from backend API
        const response = await api.get<ResponseEnvelope<UserProfile>>("/api/auth/me");
        if (isMounted && response?.data) {
          setUserProfile(response.data);
        }
      } catch {
        // Graceful error handling retaining cached/session identity
      }
    }

    loadProfile();

    return () => {
      isMounted = false;
    };
  }, []);

  // Collapse sidebar to icon rail between 768px and 1024px per UI-UX.md Section 4
  useEffect(() => {
    function handleResize() {
      if (window.innerWidth < 1024 && window.innerWidth >= 768) {
        setIsTabletCollapsed(true);
      } else {
        setIsTabletCollapsed(false);
      }
    }

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return (
    <div className="flex h-screen w-full bg-background overflow-hidden">
      {/* Desktop & Tablet Sidebar */}
      <div className="hidden md:flex shrink-0 h-full">
        <Sidebar isCollapsed={isTabletCollapsed} />
      </div>

      {/* Mobile Sidebar Sheet */}
      <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
        <SheetContent side="left" className="p-0 w-64 border-r border-border bg-card">
          <Sidebar onNavigate={() => setMobileMenuOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* Main Content Area */}
      <div className="flex flex-col flex-1 min-w-0 h-full overflow-hidden">
        <Header
          userProfile={userProfile}
          onMobileMenuToggle={() => setMobileMenuOpen(true)}
        />
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
          <div className="max-w-6xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
}
