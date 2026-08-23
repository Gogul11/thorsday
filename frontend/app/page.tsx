"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ChatComposer } from "@/components/chat-composer";
import { TaskActivity } from "@/components/task-activity";
import { TaskList, TaskRecord } from "@/components/task-list";
import { createTask, followUpTask, getTaskStatus } from "@/lib/api";

const activeStatuses = new Set(["queued", "running"]);

export default function Home() {
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const selectedTask = tasks.find((task) => task.task_id === selectedTaskId);
  const selectedTaskIsActive = Boolean(
    selectedTask && activeStatuses.has(selectedTask.status),
  );
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
      if (selectedTask) {
        const updatedTask = await followUpTask(selectedTask.task_id, prompt);
        const occurredAt = new Date().toISOString();

        setTasks((current) =>
          current.map((task) =>
            task.task_id === selectedTask.task_id
              ? {
                  ...task,
                  status: updatedTask.status,
                  response: null,
                  error: null,
                  messages: [
                    ...task.messages,
                    { role: "user", content: prompt, occurred_at: occurredAt },
                  ],
                }
              : task,
          ),
        );
        void refreshTask(selectedTask.task_id).catch(() => undefined);
      } else {
        const createdTask = await createTask(prompt);
        const occurredAt = new Date().toISOString();
        const task: TaskRecord = {
          task_id: createdTask.task_id,
          status: createdTask.status,
          prompt,
          submittedAt: occurredAt,
          response: null,
          error: null,
          events: [],
          messages: [{ role: "user", content: prompt, occurred_at: occurredAt }],
        };

        setTasks((current) => [task, ...current]);
        setSelectedTaskId(task.task_id);
        void refreshTask(task.task_id).catch(() => undefined);
      }
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Could not send message.");
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
              {selectedTask.messages.map((message, index) => (
                <article
                  className={`message ${message.role === "user" ? "user-message" : "agent-message"}`}
                  key={`${message.occurred_at}-${index}`}
                >
                  <span>{message.role === "user" ? "You" : "AgentOS"}</span>
                  {message.role === "assistant" ? (
                    <div className="markdown">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {message.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <p>{message.content}</p>
                  )}
                </article>
              ))}

              {selectedTask.error ? (
                <article className="message agent-message">
                  <span>AgentOS</span>
                  <p className="error-message">{selectedTask.error}</p>
                </article>
              ) : selectedTaskIsActive ? (
                <article className="message agent-message">
                  <span>AgentOS</span>
                  <p className="working-message">Working on this task...</p>
                </article>
              ) : null}
            </>
          )}
        </div>

        {submitError ? <p className="submit-error">{submitError}</p> : null}
        <ChatComposer
          disabled={isSubmitting || selectedTaskIsActive}
          onSubmit={submitTask}
        />
      </section>

      <TaskActivity task={selectedTask} />
    </main>
  );
}
