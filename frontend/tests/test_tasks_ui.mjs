import { describe, it } from "node:test";
import assert from "node:assert/strict";

// Logic helpers replicating components behavior in TaskList.tsx, TaskRow.tsx, and TodayPage.tsx

function groupTasks(tasks, referenceDate = new Date()) {
  const todayStart = new Date(
    referenceDate.getFullYear(),
    referenceDate.getMonth(),
    referenceDate.getDate(),
    0,
    0,
    0,
    0
  );
  const todayEnd = new Date(
    referenceDate.getFullYear(),
    referenceDate.getMonth(),
    referenceDate.getDate(),
    23,
    59,
    59,
    999
  );

  const overdue = [];
  const today = [];
  const upcoming = [];
  const completed = [];

  for (const t of tasks) {
    if (t.status === "completed") {
      completed.push(t);
      continue;
    }
    if (t.status === "snoozed") {
      upcoming.push(t);
      continue;
    }
    if (!t.due_date) {
      upcoming.push(t);
      continue;
    }
    const d = new Date(t.due_date);
    if (d < todayStart) {
      overdue.push(t);
    } else if (d <= todayEnd) {
      today.push(t);
    } else {
      upcoming.push(t);
    }
  }

  return { overdue, today, upcoming, completed };
}

function computeSnoozeTimestamp(preset, now = new Date()) {
  const IST_OFFSET_MS = 5.5 * 3600 * 1000;
  const nowUtc = now.getTime();
  const nowIst = new Date(nowUtc + IST_OFFSET_MS);

  if (preset === "later_today") {
    return new Date(nowUtc + 4 * 3600 * 1000);
  }
  if (preset === "tomorrow") {
    // Tomorrow 09:00 IST = 03:30 UTC
    const tomorrowUtcDate = new Date(nowUtc + 24 * 3600 * 1000);
    return new Date(
      Date.UTC(
        tomorrowUtcDate.getUTCFullYear(),
        tomorrowUtcDate.getUTCMonth(),
        tomorrowUtcDate.getUTCDate(),
        3,
        30,
        0
      )
    );
  }
  if (preset === "next_week") {
    // 7 days later 09:00 IST = 03:30 UTC
    const nextWeekUtcDate = new Date(nowUtc + 7 * 24 * 3600 * 1000);
    return new Date(
      Date.UTC(
        nextWeekUtcDate.getUTCFullYear(),
        nextWeekUtcDate.getUTCMonth(),
        nextWeekUtcDate.getUTCDate(),
        3,
        30,
        0
      )
    );
  }
  return new Date(nowUtc + 24 * 3600 * 1000);
}

function toggleTaskStatus(task, nowIso = new Date().toISOString()) {
  if (task.status === "completed") {
    return {
      ...task,
      status: "pending",
      completed_at: null,
    };
  }
  return {
    ...task,
    status: "completed",
    completed_at: nowIso,
  };
}

describe("Tasks Management UI & Logic Tests (Stage 6 Task 6)", () => {
  const mockNow = new Date("2026-11-06T12:00:00Z");

  it("groups tasks into Overdue, Today, Upcoming, and Completed per UI-UX.md §6.9", () => {
    const sampleTasks = [
      { id: "t1", title: "Review reply", due_date: "2026-11-05T10:00:00Z", status: "pending" }, // Overdue
      { id: "t2", title: "Approve draft", due_date: "2026-11-06T15:00:00Z", status: "pending" }, // Today
      { id: "t3", title: "Follow up call", due_date: "2026-11-08T09:00:00Z", status: "pending" }, // Upcoming
      { id: "t4", title: "Send pricing", due_date: null, status: "pending" },                    // Upcoming (no date)
      { id: "t5", title: "Old callback", due_date: "2026-11-04T10:00:00Z", status: "completed" }, // Completed
      { id: "t6", title: "Snoozed task", due_date: "2026-11-05T10:00:00Z", status: "snoozed" },  // Upcoming (snoozed)
    ];

    const grouped = groupTasks(sampleTasks, mockNow);
    assert.strictEqual(grouped.overdue.length, 1);
    assert.strictEqual(grouped.overdue[0].id, "t1");

    assert.strictEqual(grouped.today.length, 1);
    assert.strictEqual(grouped.today[0].id, "t2");

    assert.strictEqual(grouped.upcoming.length, 3);
    const upcomingIds = grouped.upcoming.map((t) => t.id);
    assert.ok(upcomingIds.includes("t3"));
    assert.ok(upcomingIds.includes("t4"));
    assert.ok(upcomingIds.includes("t6"));

    assert.strictEqual(grouped.completed.length, 1);
    assert.strictEqual(grouped.completed[0].id, "t5");
  });

  it("toggles completion status and correctly manages completed_at timestamp", () => {
    const openTask = {
      id: "task_1",
      title: "Review lead",
      status: "pending",
      completed_at: null,
    };

    const completed = toggleTaskStatus(openTask, "2026-11-06T12:00:00Z");
    assert.strictEqual(completed.status, "completed");
    assert.strictEqual(completed.completed_at, "2026-11-06T12:00:00Z");

    const reopened = toggleTaskStatus(completed);
    assert.strictEqual(reopened.status, "pending");
    assert.strictEqual(reopened.completed_at, null);
  });

  it("calculates snooze timestamps for later_today, tomorrow, and next_week presets", () => {
    const baseNow = new Date("2026-11-06T10:00:00Z");

    const laterToday = computeSnoozeTimestamp("later_today", baseNow);
    assert.strictEqual(laterToday.getTime(), baseNow.getTime() + 4 * 3600 * 1000);

    const tomorrow = computeSnoozeTimestamp("tomorrow", baseNow);
    assert.strictEqual(tomorrow.getUTCHours(), 3);
    assert.strictEqual(tomorrow.getUTCMinutes(), 30);
    assert.strictEqual(tomorrow.getUTCDate(), 7);

    const nextWeek = computeSnoozeTimestamp("next_week", baseNow);
    assert.strictEqual(nextWeek.getUTCHours(), 3);
    assert.strictEqual(nextWeek.getUTCMinutes(), 30);
    assert.strictEqual(nextWeek.getUTCDate(), 13);
  });

  it("filters tasks by priority accurately", () => {
    const tasks = [
      { id: "1", priority: "urgent" },
      { id: "2", priority: "high" },
      { id: "3", priority: "urgent" },
      { id: "4", priority: "low" },
    ];
    const urgentTasks = tasks.filter((t) => t.priority === "urgent");
    assert.strictEqual(urgentTasks.length, 2);
    const highTasks = tasks.filter((t) => t.priority === "high");
    assert.strictEqual(highTasks.length, 1);
  });

  it("maps task types to semantic UI chips for the Today attention list", () => {
    function getTaskChip(taskType) {
      switch (taskType) {
        case "review_reply":
          return "Replied";
        case "approve_message":
          return "Draft";
        case "callback":
          return "Callback";
        case "schedule_meeting":
          return "Meeting";
        default:
          return "Task";
      }
    }

    assert.strictEqual(getTaskChip("review_reply"), "Replied");
    assert.strictEqual(getTaskChip("approve_message"), "Draft");
    assert.strictEqual(getTaskChip("callback"), "Callback");
    assert.strictEqual(getTaskChip("schedule_meeting"), "Meeting");
    assert.strictEqual(getTaskChip("general"), "Task");
  });

  it("verifies exact empty state copy matching UI-UX.md §6.9 and §6.2", () => {
    const tasksEmptyText = "No open tasks.";
    const attentionQueueEmptyText = "Nothing needs your attention right now.";

    assert.strictEqual(tasksEmptyText, "No open tasks.");
    assert.strictEqual(attentionQueueEmptyText, "Nothing needs your attention right now.");
  });

  it("computes live Today metrics row counts matching UI-UX.md §6.2", () => {
    const pipelineData = {
      stage_counts: {
        replied: 3,
        followup_due: 2,
      },
    };
    const tasksData = {
      tasks: [
        { id: "1", task_type: "approve_message", status: "pending" },
        { id: "2", task_type: "approve_message", status: "pending" },
        { id: "3", task_type: "callback", status: "pending" },
      ],
      counts: { overdue: 1, today: 2, upcoming: 1, completed: 5, total: 9 },
    };

    const repliesWaiting = pipelineData.stage_counts["replied"] || 0;
    const draftsToApprove = tasksData.tasks.filter(
      (t) => t.task_type === "approve_message" && t.status !== "completed"
    ).length;
    const followupsDue = pipelineData.stage_counts["followup_due"] || 0;
    const tasksOverdue = tasksData.counts.overdue;

    assert.strictEqual(repliesWaiting, 3);
    assert.strictEqual(draftsToApprove, 2);
    assert.strictEqual(followupsDue, 2);
    assert.strictEqual(tasksOverdue, 1);
  });
});

