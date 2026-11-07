"use client";

import React, { useState } from "react";
import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Filter,
  ListTodo,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { TaskRow } from "./TaskRow";
import { api, ApiClientError } from "@/lib/api";
import type { TaskResponse } from "@/types";

interface TaskListProps {
  tasks: TaskResponse[];
  onTasksChanged: () => void;
}

export function TaskList({ tasks, onTasksChanged }: TaskListProps) {
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [isCompletedOpen, setIsCompletedOpen] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filter tasks by priority if selected
  const visibleTasks = tasks.filter((t) => {
    if (priorityFilter !== "all" && t.priority !== priorityFilter) return false;
    return true;
  });

  // Group tasks matching UI-UX.md §6.9: Overdue, Today, Upcoming, Completed
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
  const todayEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);

  const overdueTasks: TaskResponse[] = [];
  const todayTasks: TaskResponse[] = [];
  const upcomingTasks: TaskResponse[] = [];
  const completedTasks: TaskResponse[] = [];

  for (const t of visibleTasks) {
    if (t.status === "completed") {
      completedTasks.push(t);
      continue;
    }

    if (t.status === "snoozed") {
      // Snoozed tasks are upcoming until unsnoozed
      upcomingTasks.push(t);
      continue;
    }

    // Open tasks (pending / in_progress)
    if (!t.due_date) {
      upcomingTasks.push(t);
      continue;
    }

    const d = new Date(t.due_date);
    if (d < todayStart) {
      overdueTasks.push(t);
    } else if (d <= todayEnd) {
      todayTasks.push(t);
    } else {
      upcomingTasks.push(t);
    }
  }

  // Handle toggling complete status
  const handleToggleComplete = async (task: TaskResponse) => {
    const isCompleted = task.status === "completed";
    const nextStatus = isCompleted ? "pending" : "completed";
    setUpdatingId(task.id);
    setErrorMessage(null);

    try {
      await api.put(`/api/tasks/${task.id}`, { status: nextStatus });
      onTasksChanged();
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to update task";
      setErrorMessage(msg);
    } finally {
      setUpdatingId(null);
    }
  };

  // Handle snooze action
  const handleSnooze = async (
    taskId: string,
    preset: "later_today" | "tomorrow" | "next_week"
  ) => {
    setUpdatingId(taskId);
    setErrorMessage(null);

    try {
      await api.put(`/api/tasks/${taskId}`, {
        status: "snoozed",
        snooze_preset: preset,
      });
      onTasksChanged();
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to snooze task";
      setErrorMessage(msg);
    } finally {
      setUpdatingId(null);
    }
  };

  const totalOpen = overdueTasks.length + todayTasks.length + upcomingTasks.length;

  return (
    <div className="space-y-6">
      {/* Priority Filter Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-border/60">
        <div className="flex items-center gap-1.5 overflow-x-auto text-xs">
          <span className="text-muted-foreground mr-1 flex items-center gap-1 font-medium">
            <Filter className="h-3.5 w-3.5" />
            Priority:
          </span>
          {["all", "urgent", "high", "medium", "low"].map((p) => (
            <button
              key={p}
              onClick={() => setPriorityFilter(p)}
              className={`px-2.5 py-1 rounded-md capitalize font-medium transition-colors ${
                priorityFilter === p
                  ? "bg-primary text-primary-foreground shadow-xs"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              {p}
            </button>
          ))}
        </div>

        <span className="text-xs text-muted-foreground">
          <strong className="text-foreground">{totalOpen}</strong> open tasks
        </span>
      </div>

      {/* Error Banner */}
      {errorMessage && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-destructive font-semibold hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Empty open tasks state per UI-UX.md §6.9 */}
      {totalOpen === 0 && completedTasks.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 text-center rounded-xl border border-dashed border-border bg-card/40">
          <ListTodo className="h-10 w-10 text-muted-foreground/50 mb-3" />
          <h3 className="font-semibold text-sm text-foreground mb-1">
            No open tasks.
          </h3>
          <p className="text-xs text-muted-foreground max-w-sm">
            You are all caught up! Tasks will be created automatically when prospects reply or request callbacks.
          </p>
        </div>
      ) : null}

      {/* 1. OVERDUE GROUP */}
      {overdueTasks.length > 0 && (
        <section className="space-y-2.5">
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-destructive flex items-center gap-1.5">
              <AlertCircle className="h-3.5 w-3.5" />
              Overdue
            </h2>
            <Badge
              variant="outline"
              className="text-[10px] px-1.5 py-0 h-4 rounded-full border-destructive/30 text-destructive bg-destructive/10"
            >
              {overdueTasks.length}
            </Badge>
          </div>

          <div className="space-y-2">
            {overdueTasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                onToggleComplete={handleToggleComplete}
                onSnooze={handleSnooze}
                isUpdating={updatingId === task.id}
              />
            ))}
          </div>
        </section>
      )}

      {/* 2. TODAY GROUP */}
      {todayTasks.length > 0 && (
        <section className="space-y-2.5">
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-foreground flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5 text-primary" />
              Today
            </h2>
            <Badge
              variant="secondary"
              className="text-[10px] px-1.5 py-0 h-4 rounded-full font-semibold"
            >
              {todayTasks.length}
            </Badge>
          </div>

          <div className="space-y-2">
            {todayTasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                onToggleComplete={handleToggleComplete}
                onSnooze={handleSnooze}
                isUpdating={updatingId === task.id}
              />
            ))}
          </div>
        </section>
      )}

      {/* 3. UPCOMING GROUP */}
      {upcomingTasks.length > 0 && (
        <section className="space-y-2.5">
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              Upcoming
            </h2>
            <Badge
              variant="secondary"
              className="text-[10px] px-1.5 py-0 h-4 rounded-full font-semibold text-muted-foreground"
            >
              {upcomingTasks.length}
            </Badge>
          </div>

          <div className="space-y-2">
            {upcomingTasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                onToggleComplete={handleToggleComplete}
                onSnooze={handleSnooze}
                isUpdating={updatingId === task.id}
              />
            ))}
          </div>
        </section>
      )}

      {/* 4. COMPLETED GROUP (Collapsed by default per UI-UX.md §6.9) */}
      {completedTasks.length > 0 && (
        <section className="pt-2 border-t border-border/60">
          <button
            type="button"
            onClick={() => setIsCompletedOpen(!isCompletedOpen)}
            className="flex items-center justify-between w-full py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
          >
            <div className="flex items-center gap-2">
              {isCompletedOpen ? (
                <ChevronDown className="h-3.5 w-3.5" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5" />
              )}
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-good" />
                Completed
              </span>
              <Badge
                variant="outline"
                className="text-[10px] px-1.5 py-0 h-4 rounded-full font-semibold text-muted-foreground"
              >
                {completedTasks.length}
              </Badge>
            </div>

            <span className="text-[11px] font-normal normal-case text-muted-foreground">
              {isCompletedOpen ? "Hide" : "Show"}
            </span>
          </button>

          {isCompletedOpen && (
            <div className="space-y-2 mt-2">
              {completedTasks.map((task) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  onToggleComplete={handleToggleComplete}
                  onSnooze={handleSnooze}
                  isUpdating={updatingId === task.id}
                />
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

