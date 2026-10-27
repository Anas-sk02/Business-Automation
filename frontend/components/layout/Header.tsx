"use client";

import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { createClient } from "@/lib/supabase";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Bell,
  Menu,
  Sun,
  Moon,
  Laptop,
  LogOut,
  Settings,
} from "lucide-react";
import type { UserProfile } from "@/types";

interface HeaderProps {
  userProfile?: UserProfile | null;
  onMobileMenuToggle?: () => void;
}

export function Header({ userProfile, onMobileMenuToggle }: HeaderProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { setTheme, theme } = useTheme();
  const supabase = createClient();

  // Determine dynamic title from pathname
  const getPageTitle = (path: string): string => {
    if (path === "/") return "Today";
    if (path.startsWith("/campaigns/new")) return "New campaign";
    if (path.startsWith("/campaigns")) return "Campaigns";
    if (path.startsWith("/pipeline")) return "Pipeline";
    if (path.startsWith("/tasks")) return "Tasks";
    if (path.startsWith("/analytics")) return "Analytics";
    if (path.startsWith("/templates")) return "Templates";
    if (path.startsWith("/settings")) return "Settings";
    return "SignalForge";
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  };

  const displayName = userProfile?.full_name || userProfile?.email || "Account";
  const userInitial = (displayName[0] || "U").toUpperCase();

  return (
    <header className="h-14 bg-card border-b border-border px-4 md:px-6 flex items-center justify-between shrink-0 select-none">
      {/* Left: Mobile hamburger + Page Title */}
      <div className="flex items-center gap-3">
        {onMobileMenuToggle && (
          <button
            onClick={onMobileMenuToggle}
            className="p-1.5 -ml-1.5 md:hidden text-muted-foreground hover:text-foreground rounded-md hover:bg-muted/50"
            aria-label="Open navigation menu"
          >
            <Menu className="h-5 w-5" />
          </button>
        )}
        <h1 className="text-base font-semibold text-foreground tracking-tight">
          {getPageTitle(pathname)}
        </h1>
      </div>

      {/* Right: Notifications popover + User dropdown menu */}
      <div className="flex items-center gap-2">
        {/* Notification Bell */}
        <DropdownMenu>
          <DropdownMenuTrigger
            className="inline-flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            aria-label="Notifications"
          >
            <Bell className="h-4 w-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-64 p-3 space-y-2">
            <div className="flex justify-between items-center pb-2 border-b border-border">
              <span className="text-xs font-semibold text-foreground">Notifications</span>
            </div>
            {/* Honest Empty State per UI-UX.md Section 4 */}
            <div className="py-6 text-center text-xs text-muted-foreground">
              No notifications.
            </div>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger
            className="inline-flex items-center gap-2 h-8 pl-2 pr-2.5 rounded-md text-xs font-medium hover:bg-muted/50 transition-colors"
          >
            <div className="w-5 h-5 rounded-full bg-secondary text-primary flex items-center justify-center font-bold text-[10px]">
              {userInitial}
            </div>
            <span className="max-w-[120px] truncate hidden sm:inline">
              {displayName}
            </span>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-xs font-medium leading-none text-foreground truncate">
                  {userProfile?.full_name || "User"}
                </p>
                <p className="text-[11px] leading-none text-muted-foreground truncate">
                  {userProfile?.email}
                </p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />

            <DropdownMenuItem
              onClick={() => router.push("/settings")}
              className="cursor-pointer text-xs flex items-center gap-2"
            >
              <Settings className="h-3.5 w-3.5" />
              Settings & profile
            </DropdownMenuItem>

            <DropdownMenuSeparator />

            {/* Theme Switcher per UI-UX.md Section 4 */}
            <DropdownMenuLabel className="text-[11px] text-muted-foreground uppercase tracking-wider py-1 font-medium">
              Theme
            </DropdownMenuLabel>
            <DropdownMenuItem
              onClick={() => setTheme("light")}
              className={`text-xs flex items-center gap-2 cursor-pointer ${
                theme === "light" ? "text-primary font-medium" : ""
              }`}
            >
              <Sun className="h-3.5 w-3.5" />
              Light
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => setTheme("dark")}
              className={`text-xs flex items-center gap-2 cursor-pointer ${
                theme === "dark" ? "text-primary font-medium" : ""
              }`}
            >
              <Moon className="h-3.5 w-3.5" />
              Dark
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => setTheme("system")}
              className={`text-xs flex items-center gap-2 cursor-pointer ${
                theme === "system" ? "text-primary font-medium" : ""
              }`}
            >
              <Laptop className="h-3.5 w-3.5" />
              System
            </DropdownMenuItem>

            <DropdownMenuSeparator />

            <DropdownMenuItem
              onClick={handleSignOut}
              className="text-xs text-problem focus:text-problem cursor-pointer flex items-center gap-2"
            >
              <LogOut className="h-3.5 w-3.5" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
