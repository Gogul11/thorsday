"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ChatComposer } from "./chat-composer";
import type { TaskRecord } from "@/lib/types";

type ChatPanelProps = {
  selectedTask: TaskRecord | undefined;
  isSubmitting: boolean;
  submitError: string | null;
  onSubmit: (prompt: string) => Promise<void>;
};

function EmptyConversation() {
  return (
    <div className="empty-conversation">
      <h2>Send a task</h2>
      <p>Use the chat box to start an agent task. Its progress will appear on the right.</p>
    </div>
  );
}

function AgentResponse({ task }: { task: TaskRecord }) {
  if (task.response) {
    return (
      <div className="markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.response}</ReactMarkdown>
      </div>
    );
  }
  if (task.error) {
    return <p className="error-message">{task.error}</p>;
  }
  return <p className="working-message">Working on this task…</p>;
}

function TaskConversation({ task }: { task: TaskRecord }) {
  return (
    <>
      <article className="message user-message">
        <span>You</span>
        <p>{task.prompt}</p>
      </article>

      <article className="message agent-message">
        <span>AgentOS</span>
        <AgentResponse task={task} />
      </article>
    </>
  );
}

export function ChatPanel({
  selectedTask,
  isSubmitting,
  submitError,
  onSubmit,
}: ChatPanelProps) {
  return (
    <section className="chat-panel">
      <header className="chat-header">
        <div>
          <p className="eyebrow">Agent workspace</p>
          <h1>{selectedTask ? "Task" : "New task"}</h1>
        </div>
        {selectedTask ? (
          <span className="plain-status">{selectedTask.status}</span>
        ) : null}
      </header>

      <div className="conversation">
        {selectedTask ? (
          <TaskConversation task={selectedTask} />
        ) : (
          <EmptyConversation />
        )}
      </div>

      {submitError ? <p className="submit-error">{submitError}</p> : null}
      <ChatComposer disabled={isSubmitting} onSubmit={onSubmit} />
    </section>
  );
}
