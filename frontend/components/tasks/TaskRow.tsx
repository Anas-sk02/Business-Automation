"use client";

import React from "react";
import Link from "next/link";
import {
  Clock,
  MoreVertical,
  ExternalLink,
  Building,
  AlertCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import type { TaskResponse, TaskPriority } from "@/types";

interface TaskRowProps {
  task: TaskResponse;
  onToggleComplete: (task: TaskResponse) => void;
  onSnooze: (taskId: string, preset: "later_today" | "tomorrow" | "next_week") => void;
  isUpdating?: boolean;
}

export function TaskRow({
  task,
  onToggleComplete,
  onSnooze,
  isUpdating = false,
}: TaskRowProps) {
  const isCompleted = task.status === "completed";
  const isSnoozed = task.status === "snoozed";

  // Check if overdue: open task with due_date in the past
  const now = new Date();
  const dueDate = task.due_date ? new Date(task.due_date) : null;
  const isOverdue = !isCompleted && !isSnoozed && dueDate !== null && dueDate < now;

  // Format due date / time
  let dueDisplay = "No due date";
  if (dueDate) {
    const isToday =
      dueDate.getDate() === now.getDate() &&
      dueDate.getMonth() === now.getMonth() &&
      dueDate.getFullYear() === now.getFullYear();

    const timeStr = dueDate.toLocaleTimeString("en-IN", {
      hour: "numeric",
      minute: "2-digit",
    });

    if (isToday) {
      dueDisplay = `Today at ${timeStr}`;
    } else {
      const dateStr = dueDate.toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
      });
      dueDisplay = `${dateStr}, ${timeStr}`;
    }
  }

  // Priority badge styling
  const getPriorityBadge = (priority: TaskPriority | string) => {
    switch (priority) {
      case "urgent":
        return "text-destructive bg-destructive/10 border-destructive/30";
      case "high":
        return "text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800";
      case "medium":
        return "text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800";
      default:
        return "text-muted-foreground bg-muted border-border";
    }
  };

  return (
    <div
      className={`group flex items-start sm:items-center justify-between gap-3 p-3.5 rounded-lg border bg-card transition-all duration-150 ${
        isCompleted
          ? "opacity-60 bg-muted/20 border-border/60"
          : isOverdue
          ? "border-destructive/30 hover:border-destructive/50 bg-destructive/5"
          : "border-border hover:border-border/90 hover:shadow-2xs"
      } ${isUpdating ? "opacity-50 pointer-events-none" : ""}`}
    >
      {/* Left: Checkbox & Task Content */}
      <div className="flex items-start gap-3 min-w-0 flex-1">
        {/* Completion Checkbox */}
        <input
          type="checkbox"
          checked={isCompleted}
          disabled={isUpdating}
          onChange={() => onToggleComplete(task)}
          aria-label={`Mark task '${task.title}' as ${isCompleted ? "open" : "completed"}`}
          className="mt-0.5 sm:mt-0 h-4 w-4 shrink-0 rounded-sm border-input text-primary focus:ring-1 focus:ring-primary cursor-pointer disabled:opacity-50"
        />

        {/* Task Title & Lead Link */}
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`text-sm font-medium text-foreground ${
                isCompleted ? "line-through text-muted-foreground" : ""
              }`}
            >
              {task.title}
            </span>

            {/* Linked Lead Name */}
            {task.lead_id && (
              <Link
                href={`/leads/${task.lead_id}`}
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline font-medium truncate max-w-[200px]"
                title={task.lead_name || "View lead"}
              >
                <span>{task.lead_name || "Lead detail"}</span>
                <ExternalLink className="h-2.5 w-2.5 shrink-0 opacity-70" />
              </Link>
            )}

            {/* Campaign Name */}
            {task.campaign_name && (
              <span className="text-[11px] text-muted-foreground flex items-center gap-1 truncate max-w-[150px]">
                <Building className="h-2.5 w-2.5 opacity-60 shrink-0" />
                {task.campaign_name}
              </span>
            )}
          </div>

          {/* Description if present */}
          {task.description && (
            <p className="text-xs text-muted-foreground line-clamp-1">
              {task.description}
            </p>
          )}
        </div>
      </div>

      {/* Right: Due Time, Priority & Snooze Actions */}
      <div className="flex items-center gap-2.5 shrink-0">
        {/* Due Time */}
        <span
          className={`text-xs flex items-center gap-1 font-medium ${
            isOverdue
              ? "text-destructive font-semibold"
              : isCompleted
              ? "text-muted-foreground line-through"
              : "text-muted-foreground"
          }`}
          title={dueDate ? dueDate.toLocaleString("en-IN") : "No due date"}
        >
          {isOverdue ? (
            <AlertCircle className="h-3 w-3 shrink-0 text-destructive" />
          ) : (
            <Clock className="h-3 w-3 shrink-0 opacity-60" />
          )}
          <span className="hidden sm:inline">{dueDisplay}</span>
          <span className="sm:hidden">
            {dueDate
              ? dueDate.toLocaleDateString("en-IN", { day: "numeric", month: "short" })
              : "No date"}
          </span>
        </span>

        {/* Priority Badge */}
        <Badge
          variant="outline"
          className={`text-[10px] uppercase font-semibold tracking-wider px-1.5 py-0 rounded-xs border capitalize ${getPriorityBadge(
            task.priority
          )}`}
        >
          {task.priority}
        </Badge>

        {/* Snooze Dropdown Menu (only if not completed) */}
        {!isCompleted && (
          <DropdownMenu>
            <DropdownMenuTrigger
              className="h-7 w-7 inline-flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted"
              title="Snooze task"
              aria-label={`Snooze task '${task.title}'`}
            >
              <MoreVertical className="h-3.5 w-3.5" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40 text-xs">
              <DropdownMenuGroup>
                <DropdownMenuLabel className="text-xs font-semibold">
                  Snooze task
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => onSnooze(task.id, "later_today")}
                  className="cursor-pointer text-xs"
                >
                  Later today (+4h)
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => onSnooze(task.id, "tomorrow")}
                  className="cursor-pointer text-xs"
                >
                  Tomorrow (9:00 AM)
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => onSnooze(task.id, "next_week")}
                  className="cursor-pointer text-xs"
                >
                  Next week (+7d)
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </div>
  );
}

