"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ChatComposer } from "@/components/chat-composer";
import { TaskActivity } from "@/components/task-activity";
import { TaskList, TaskRecord } from "@/components/task-list";
import { createTask, getTaskStatus } from "@/lib/api";

const activeStatuses = new Set(["queued", "running"]);

export default function Home() {
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const selectedTask = tasks.find((task) => task.task_id === selectedTaskId);
  const activeTaskIds = useMemo(
    () =>
      tasks
        .filter((task) => activeStatuses.has(task.status))
        .map((task) => task.task_id),
    [tasks],
  );
  const activeTaskKey = activeTaskIds.join(",");

  const refreshTask = useCallback(async (taskId: string) => {
    const status = await getTaskStatus(taskId);
    setTasks((current) =>
      current.map((task) =>
        task.task_id === taskId ? { ...task, ...status } : task,
      ),
    );
  }, []);

  useEffect(() => {
    if (!activeTaskKey) {
      return;
    }

    const refreshActiveTasks = () => {
      activeTaskKey.split(",").forEach((taskId) => {
        void refreshTask(taskId).catch(() => undefined);
      });
    };

    refreshActiveTasks();
    const timer = window.setInterval(refreshActiveTasks, 1200);
    return () => window.clearInterval(timer);
  }, [activeTaskKey, refreshTask]);

  async function submitTask(prompt: string) {
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const createdTask = await createTask(prompt);
      const task: TaskRecord = {
        task_id: createdTask.task_id,
        status: createdTask.status,
        prompt,
        submittedAt: new Date().toISOString(),
        response: null,
        error: null,
        events: [],
      };

      setTasks((current) => [task, ...current]);
      setSelectedTaskId(task.task_id);
      void refreshTask(task.task_id).catch(() => undefined);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Could not create task.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className={`workspace ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <TaskList
        tasks={tasks}
        selectedTaskId={selectedTaskId}
        onSelect={setSelectedTaskId}
        onNewTask={() => {
          setSelectedTaskId(null);
          setSidebarCollapsed(false);
        }}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((current) => !current)}
      />

      <section className="chat-panel">
        <header className="chat-header">
          <div>
            <p className="eyebrow">Agent workspace</p>
            <h1>{selectedTask ? "Task" : "New task"}</h1>
          </div>
          {selectedTask ? <span className="plain-status">{selectedTask.status}</span> : null}
        </header>

        <div className="conversation">
          {!selectedTask ? (
            <div className="empty-conversation">
              <h2>Send a task</h2>
              <p>Use the chat box to start an agent task. Its progress will appear on the right.</p>
            </div>
          ) : (
            <>
              <article className="message user-message">
                <span>You</span>
                <p>{selectedTask.prompt}</p>
              </article>

              <article className="message agent-message">
                <span>AgentOS</span>
                {selectedTask.response ? (
                  <div className="markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {selectedTask.response}
                    </ReactMarkdown>
                  </div>
                ) : selectedTask.error ? (
                  <p className="error-message">{selectedTask.error}</p>
                ) : (
                  <p className="working-message">Working on this task…</p>
                )}
              </article>
            </>
          )}
        </div>

        {submitError ? <p className="submit-error">{submitError}</p> : null}
        <ChatComposer disabled={isSubmitting} onSubmit={submitTask} />
      </section>

      <TaskActivity task={selectedTask} />
    </main>
  );
}
