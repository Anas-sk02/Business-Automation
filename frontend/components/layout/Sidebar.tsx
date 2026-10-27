"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  CalendarCheck2,
  Target,
  Columns3,
  CheckSquare,
  BarChart3,
  MessageSquareQuote,
  Settings,
} from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

const mainNavItems: NavItem[] = [
  { label: "Today", href: "/", icon: CalendarCheck2 },
  { label: "Campaigns", href: "/campaigns", icon: Target },
  { label: "Pipeline", href: "/pipeline", icon: Columns3 },
  { label: "Tasks", href: "/tasks", icon: CheckSquare },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
];

const secondaryNavItems: NavItem[] = [
  { label: "Templates", href: "/templates", icon: MessageSquareQuote },
  { label: "Settings", href: "/settings", icon: Settings },
];

interface SidebarProps {
  isCollapsed?: boolean;
  onNavigate?: () => void;
}

export function Sidebar({ isCollapsed = false, onNavigate }: SidebarProps) {
  const pathname = usePathname();

  const isItemActive = (href: string) => {
    if (href === "/") {
      return pathname === "/";
    }
    return pathname.startsWith(href);
  };

  return (
    <aside
      className={`h-full bg-card border-r border-border flex flex-col justify-between transition-all duration-200 select-none ${
        isCollapsed ? "w-16" : "w-56"
      }`}
    >
      <div className="flex flex-col flex-1 py-4">
        {/* Brand / Logo */}
        <div className="px-4 mb-6 flex items-center h-8">
          <Link
            href="/"
            onClick={onNavigate}
            className="flex items-center gap-2 text-foreground font-semibold tracking-tight text-base"
          >
            <div className="w-6 h-6 rounded-md bg-primary flex items-center justify-center text-primary-foreground font-bold text-xs">
              S
            </div>
            {!isCollapsed && <span>SignalForge</span>}
          </Link>
        </div>

        {/* Primary Navigation */}
        <nav className="space-y-1 px-2">
          {mainNavItems.map((item) => {
            const Icon = item.icon;
            const active = isItemActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                title={isCollapsed ? item.label : undefined}
                className={`flex items-center gap-3 px-3 py-2 text-sm rounded-md transition-colors ${
                  active
                    ? "bg-secondary text-primary font-medium"
                    : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                } ${isCollapsed ? "justify-center px-0" : ""}`}
              >
                <Icon className="h-[18px] w-[18px] shrink-0" />
                {!isCollapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Secondary Navigation (Templates & Settings) */}
      <div className="p-2 border-t border-border space-y-1">
        {secondaryNavItems.map((item) => {
          const Icon = item.icon;
          const active = isItemActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              title={isCollapsed ? item.label : undefined}
              className={`flex items-center gap-3 px-3 py-2 text-sm rounded-md transition-colors ${
                active
                  ? "bg-secondary text-primary font-medium"
                  : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
              } ${isCollapsed ? "justify-center px-0" : ""}`}
            >
              <Icon className="h-[18px] w-[18px] shrink-0" />
              {!isCollapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </div>
    </aside>
  );
}
