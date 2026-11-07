"use client";

import React, { useEffect, useState, useCallback } from "react";
import { CheckSquare, RefreshCw, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TaskList } from "@/components/tasks/TaskList";
import { api, ApiClientError } from "@/lib/api";
import type { TaskListResponse } from "@/types";

export default function TasksPage() {
  const [tasksData, setTasksData] = useState<TaskListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadTasks = useCallback(async () => {
    try {
      const res = await api.get<{ data: TaskListResponse }>("/api/tasks");
      setTasksData(res.data);
      setError(null);
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.message : "Failed to load tasks";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  return (
    <div className="flex flex-col flex-1 p-6 max-w-5xl mx-auto w-full space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <CheckSquare className="h-5 w-5 text-primary" />
            Tasks
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Follow-ups, approvals, callbacks, and daily outreach priorities.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setLoading(true);
            loadTasks();
          }}
          disabled={loading}
          className="text-xs gap-1.5 h-8 font-medium"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Loading Skeleton */}
      {loading && (
        <div className="space-y-4">
          <div className="flex gap-2">
            <Skeleton className="h-7 w-20 rounded-md" />
            <Skeleton className="h-7 w-20 rounded-md" />
            <Skeleton className="h-7 w-20 rounded-md" />
          </div>
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-16 rounded-lg border border-border/50 bg-card p-3 flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <Skeleton className="h-4 w-4 rounded-sm" />
                  <div className="space-y-1.5">
                    <Skeleton className="h-4 w-48" />
                    <Skeleton className="h-3 w-32" />
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-5 w-14 rounded-xs" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error Banner */}
      {!loading && error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center space-y-3">
          <div className="flex items-center justify-center text-destructive gap-2 font-medium text-sm">
            <AlertCircle className="h-5 w-5" />
            <span>{error}</span>
          </div>
          <Button size="sm" variant="outline" onClick={loadTasks} className="text-xs">
            Try Again
          </Button>
        </div>
      )}

      {/* Task List Component */}
      {!loading && !error && tasksData && (
        <TaskList tasks={tasksData.tasks} onTasksChanged={loadTasks} />
      )}
    </div>
  );
}

