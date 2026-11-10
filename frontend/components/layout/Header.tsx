"use client";

import { useEffect, useState, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { createClient } from "@/lib/supabase";
import { api } from "@/lib/api";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
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
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
} from "lucide-react";
import type {
  UserProfile,
  AppNotification,
  NotificationListResponse,
  ResponseEnvelope,
} from "@/types";

interface HeaderProps {
  userProfile?: UserProfile | null;
  onMobileMenuToggle?: () => void;
}

function formatRelativeTime(dateString?: string | null): string {
  if (!dateString) return "";
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return "";
  const now = new Date();
  const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

function getNotificationIcon(type: string) {
  switch (type) {
    case "action_required":
      return <AlertCircle className="h-4 w-4 text-amber-500 shrink-0" />;
    case "warning":
      return <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />;
    case "success":
      return <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />;
    case "error":
      return <AlertCircle className="h-4 w-4 text-rose-500 shrink-0" />;
    case "info":
    default:
      return <Info className="h-4 w-4 text-blue-500 shrink-0" />;
  }
}

export function Header({ userProfile, onMobileMenuToggle }: HeaderProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { setTheme, theme } = useTheme();
  const supabase = createClient();

  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);

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

  const loadNotifications = useCallback(async () => {
    try {
      const res = await api.get<ResponseEnvelope<NotificationListResponse>>("/api/notifications");
      const payload = res?.data || (res as unknown as NotificationListResponse);
      if (payload) {
        setNotifications(payload.notifications || []);
        setUnreadCount(payload.unread_count || 0);
      }
    } catch {
      // Graceful fallback if offline or backend unauthenticated
    }
  }, []);

  // Poll notifications every 30 seconds when tab is visible
  useEffect(() => {
    loadNotifications();

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        loadNotifications();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    const interval = setInterval(() => {
      if (document.visibilityState === "visible") {
        loadNotifications();
      }
    }, 30000);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      clearInterval(interval);
    };
  }, [loadNotifications]);

  const handleMarkAllRead = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.put("/api/notifications/read-all");
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, is_read: true, read_at: new Date().toISOString() }))
      );
      setUnreadCount(0);
    } catch {
      // Ignore error
    }
  };

  const handleNotificationClick = async (item: AppNotification) => {
    try {
      if (!item.is_read) {
        await api.put(`/api/notifications/${item.id}/read`);
        setNotifications((prev) =>
          prev.map((n) =>
            n.id === item.id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n
          )
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      }
    } catch {
      // Non-blocking
    }

    setIsNotificationsOpen(false);

    // Sanitize link_url to prevent open redirect vulnerabilities
    if (
      item.link_url &&
      typeof item.link_url === "string" &&
      item.link_url.startsWith("/") &&
      !item.link_url.startsWith("//")
    ) {
      router.push(item.link_url);
    }
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
        <DropdownMenu
          open={isNotificationsOpen}
          onOpenChange={(open) => {
            setIsNotificationsOpen(open);
            if (open) {
              loadNotifications();
            }
          }}
        >
          <DropdownMenuTrigger
            className="relative inline-flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
          >
            <Bell className="h-4 w-4" />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[9px] font-bold text-primary-foreground animate-in zoom-in-50">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-80 sm:w-96 p-3 space-y-2">
            <div className="flex justify-between items-center pb-2 border-b border-border">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-foreground">Notifications</span>
                {unreadCount > 0 && (
                  <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-primary/10 text-primary">
                    {unreadCount} new
                  </span>
                )}
              </div>
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="text-[11px] text-muted-foreground hover:text-foreground font-medium transition-colors"
                >
                  Mark all read
                </button>
              )}
            </div>

            {notifications.length === 0 ? (
              /* Honest Empty State */
              <div className="py-6 px-2 text-center text-xs text-muted-foreground space-y-1">
                <p className="font-medium text-foreground">No notifications</p>
                <p className="text-[11px] leading-relaxed">
                  When campaigns finish running or leads reply, you’ll see them here.
                </p>
              </div>
            ) : (
              <div className="max-h-80 overflow-y-auto -mx-1 px-1 divide-y divide-border/40">
                {notifications.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => handleNotificationClick(item)}
                    className={`p-2.5 rounded-md cursor-pointer transition-colors text-left flex gap-2.5 items-start ${
                      item.is_read
                        ? "hover:bg-muted/40 opacity-75 hover:opacity-100"
                        : "bg-primary/5 hover:bg-primary/10"
                    }`}
                  >
                    <div className="mt-0.5">{getNotificationIcon(item.type)}</div>
                    <div className="flex-1 min-w-0 space-y-0.5">
                      <div className="flex items-center justify-between gap-1">
                        <p
                          className={`text-xs truncate ${
                            item.is_read
                              ? "font-normal text-foreground"
                              : "font-semibold text-foreground"
                          }`}
                        >
                          {item.title}
                        </p>
                        <span className="text-[10px] text-muted-foreground shrink-0">
                          {formatRelativeTime(item.created_at)}
                        </span>
                      </div>
                      <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                        {item.message}
                      </p>
                    </div>
                    {!item.is_read && (
                      <span className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                    )}
                  </div>
                ))}
              </div>
            )}
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
            <DropdownMenuGroup>
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
            </DropdownMenuGroup>
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
            <DropdownMenuGroup>
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
            </DropdownMenuGroup>

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
