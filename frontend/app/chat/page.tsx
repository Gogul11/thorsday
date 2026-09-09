"use client";

import { useEffect, useState } from "react";

import ChatPanel from "@/components/chat/ChatPanel";
import { TaskActivity } from "@/components/activity/TaskActivity";
import { TaskList } from "@/components/sidebar/TaskList";
import { useTaskSubscriptions } from "@/hooks/useTaskSubscriptions";
import { createTask, getTasks, getTask } from "@/api/tasks";

import type { TaskRecord } from "@/types";

export default function ChatPage() {
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // ---------------------------------------------------------------------------
  // Subscribe to live events for queued/running tasks
  // ---------------------------------------------------------------------------
  useTaskSubscriptions(tasks, setTasks);

  // ---------------------------------------------------------------------------
  // Load task history on mount
  // ---------------------------------------------------------------------------
  useEffect(() => {
    async function loadHistory() {
      try {
        const history = await getTasks();

        setTasks(
          history.map((task) => ({
            ...task,
            // Historical tasks don't have an active websocket subscription.
            req_id: "",
            events: [],
            messages: task.messages ?? [],
          })),
        );
      } catch {
        // History is non-critical.
      }
    }

    void loadHistory();
  }, []);

  // ---------------------------------------------------------------------------
  // Currently selected task
  // ---------------------------------------------------------------------------
  const selectedTask =
    tasks.find(
      (task) =>
        (task.task_id && task.task_id === selectedTaskId) ||
        (task.req_id && task.req_id === selectedTaskId),
    ) ?? null;

  // ---------------------------------------------------------------------------
  // Select task from sidebar
  // ---------------------------------------------------------------------------
  async function handleSelectTask(taskId: string) {
    setSelectedTaskId(taskId);

    const existing = tasks.find(
      (task) =>
        (task.task_id && task.task_id === taskId) ||
        (task.req_id && task.req_id === taskId),
    );

    // If messages are already loaded, no need to fetch again.
    if (existing && (existing.messages ?? []).length > 0) {
      return;
    }

    // We can only fetch full task details using a persistent task_id.
    const persistentId = existing?.task_id ?? taskId;

    if (!persistentId) {
      return;
    }

    // A req_id is temporary and cannot be used for getTask().
    if (existing?.req_id === persistentId && !existing?.task_id) {
      return;
    }

    try {
      const full = await getTask(persistentId);

      if (!full) {
        return;
      }

      setTasks((current) =>
        current.map((task) =>
          task.task_id === persistentId
            ? {
                ...task,
                messages: full.messages ?? [],
                response: full.response ?? task.response,
              }
            : task,
        ),
      );
    } catch {
      // Ignore detail-fetch errors.
    }
  }

  // ---------------------------------------------------------------------------
  // Submit a new task or follow-up
  // ---------------------------------------------------------------------------
  async function submitTask(prompt: string) {
    setIsSubmitting(true);
    setSubmitError(null);

    // A completed task with a persistent task_id becomes a follow-up.
    const followUpTaskId =
      selectedTask?.status === "completed" && selectedTask.task_id
        ? selectedTask.task_id
        : "";

    try {
      const created = await createTask(prompt, followUpTaskId);

      // -----------------------------------------------------------------------
      // Follow-up
      // -----------------------------------------------------------------------
      if (followUpTaskId) {
        const timestamp = new Date().toISOString();

        setTasks((current) =>
          current.map((task) =>
            task.task_id === followUpTaskId
              ? {
                  ...task,
                  req_id: created.req_id,
                  status: "queued",
                  error: null,
                  response: null,
                  delete_confirmation: null,
                  messages: [
                    ...(task.messages ?? []),
                    {
                      role: "human" as const,
                      content: prompt,
                      timestamp,
                    },
                  ],
                }
              : task,
          ),
        );

        // Keep the same task selected.
        setSelectedTaskId(followUpTaskId);

        return;
      }

      // -----------------------------------------------------------------------
      // New task
      // -----------------------------------------------------------------------
      const timestamp = new Date().toISOString();

      const task: TaskRecord = {
        task_id: "",
        req_id: created.req_id,
        title: prompt.slice(0, 80),
        created_at: timestamp,
        status: created.status,
        messages: [
          {
            role: "human",
            content: prompt,
            timestamp,
          },
        ],
        response: null,
        error: null,
        events: [],
        plan: [],
        delete_confirmation: null,
      };

      setTasks((current) => [task, ...current]);

      // Temporarily select using req_id.
      // useEffect below switches this to task_id once task.CREATED arrives.
      setSelectedTaskId(created.req_id);
    } catch (error) {
      setSubmitError(
        error instanceof Error
          ? error.message
          : "Could not submit task.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Replace temporary req_id selection with persistent task_id
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!selectedTaskId) {
      return;
    }

    const task = tasks.find(
      (item) =>
        item.req_id === selectedTaskId &&
        Boolean(item.task_id) &&
        item.task_id !== selectedTaskId,
    );

    if (task?.task_id) {
      setSelectedTaskId(task.task_id);
    }
  }, [tasks, selectedTaskId]);

  // ---------------------------------------------------------------------------
  // Close delete confirmation
  // ---------------------------------------------------------------------------
  function handleDeleteConfirmationClose() {
    if (!selectedTask) {
      return;
    }

    setTasks((current) =>
      current.map((task) => {
        const matches =
          (selectedTask.task_id &&
            task.task_id === selectedTask.task_id) ||
          (selectedTask.req_id &&
            task.req_id === selectedTask.req_id);

        if (!matches) {
          return task;
        }

        return {
          ...task,
          delete_confirmation: null,
        };
      }),
    );
  }

  return (
    <main
      className={`grid h-dvh min-h-screen overflow-hidden ${
        sidebarCollapsed
          ? "grid-cols-[64px_minmax(420px,1fr)_310px]"
          : "grid-cols-[228px_minmax(420px,1fr)_310px]"
      }`}
    >
      {/* Sidebar */}
      <TaskList
        tasks={tasks}
        selectedTaskId={selectedTaskId ?? ""}
        onSelect={handleSelectTask}
        onNewTask={() => {
          setSelectedTaskId(null);
          setSidebarCollapsed(false);
        }}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((current) => !current)}
      />

      {/* Chat */}
      <ChatPanel
        selectedTask={selectedTask}
        isSubmitting={isSubmitting}
        submitError={submitError}
        onSubmit={submitTask}
        onDeleteConfirmationClose={handleDeleteConfirmationClose}
      />

      {/* Activity */}
      <TaskActivity task={selectedTask} />
    </main>
  );
}