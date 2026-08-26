"use client";

import { useState } from "react";

import { ChatPanel } from "@/components/chat/ChatPanel";
import { TaskActivity } from "@/components/activity/TaskActivity";
import { TaskList } from "@/components/sidebar/TaskList";
import { useTaskSubscriptions } from "@/hooks/useTaskSubscriptions";
import { createTask } from "@/api/tasks";
import type { TaskRecord } from "@/types";

export default function ChatPage() {
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useTaskSubscriptions(tasks, setTasks);

  const selectedTask = tasks.find((t) => t.task_id === selectedTaskId);

  async function submitTask(prompt: string) {
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const created = await createTask(prompt);
      const task: TaskRecord = {
        task_id: created.task_id,
        status: created.status,
        prompt,
        submittedAt: new Date().toISOString(),
        response: null,
        error: null,
        events: [],
      };

      setTasks((current) => [task, ...current]);
      setSelectedTaskId(task.task_id);
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : "Could not create task.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main
      className={`grid h-dvh min-h-screen overflow-hidden ${
        sidebarCollapsed
          ? "grid-cols-[64px_minmax(420px,1fr)_310px]"
          : "grid-cols-[228px_minmax(420px,1fr)_310px]"
      }`}
    >
      <TaskList
        tasks={tasks}
        selectedTaskId={selectedTaskId}
        onSelect={setSelectedTaskId}
        onNewTask={() => {
          setSelectedTaskId(null);
          setSidebarCollapsed(false);
        }}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((c) => !c)}
      />

      <ChatPanel
        selectedTask={selectedTask}
        isSubmitting={isSubmitting}
        submitError={submitError}
        onSubmit={submitTask}
      />

      <TaskActivity task={selectedTask} />
    </main>
  );
}
