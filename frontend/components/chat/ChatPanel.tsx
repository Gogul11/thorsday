"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ChatComposer } from "./ChatComposer";
import type { TaskMessage, TaskRecord } from "@/types";

type ChatPanelProps = {
  selectedTask: TaskRecord | undefined;
  isSubmitting: boolean;
  submitError: string | null;
  onSubmit: (prompt: string) => Promise<void>;
};

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyConversation() {
  return (
    <div className="mt-[13vh] text-[#74746f]">
      <h2 className="mb-2 text-[#1e1e1c] text-xl">Send a task</h2>
      <p className="max-w-[420px] text-sm leading-[1.55]">
        Use the chat box to start an agent task. Its progress will appear on
        the right.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Single message bubble
// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: TaskMessage }) {
  const isHuman = message.role === "human";

  return (
    <article
      className={`mb-5 border border-[#deded9] rounded-[5px] px-4 py-[15px] ${
        isHuman ? "bg-[#eef2f7]" : "bg-[#fafaf8]"
      }`}
    >
      <span className="block mb-2 text-[#74746f] text-xs font-bold">
        {isHuman ? "You" : "AgentOS"}
      </span>

      {isHuman ? (
        <p className="mb-0 text-sm leading-[1.65] whitespace-pre-wrap">
          {message.content}
        </p>
      ) : (
        <div
          className="
            text-sm leading-[1.65]
            [&>:first-child]:mt-0 [&>:last-child]:mb-0
            [&_h1]:mt-[22px] [&_h1]:mb-[9px] [&_h1]:text-base
            [&_h2]:mt-[22px] [&_h2]:mb-[9px] [&_h2]:text-base
            [&_h3]:mt-[22px] [&_h3]:mb-[9px] [&_h3]:text-base
            [&_ul]:my-[10px] [&_ul]:pl-[22px] [&_ul]:leading-[1.65]
            [&_ol]:my-[10px] [&_ol]:pl-[22px] [&_ol]:leading-[1.65]
            [&_li+li]:mt-[3px]
            [&_pre]:overflow-x-auto [&_pre]:p-2.5 [&_pre]:rounded [&_pre]:bg-[#f0f0ec]
            [&_code]:bg-[#f0f0ec] [&_code]:text-[#5a5a54] [&_code]:font-mono [&_code]:text-[10px]
            [&_:not(pre)>code]:px-1 [&_:not(pre)>code]:rounded-[3px]
          "
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>
      )}
    </article>
  );
}

// ---------------------------------------------------------------------------
// "Agent is working" placeholder shown while the current turn is in-flight
// ---------------------------------------------------------------------------

function WorkingPlaceholder({ prompt }: { prompt: string }) {
  return (
    <>
      <article className="mb-5 border border-[#deded9] rounded-[5px] px-4 py-[15px] bg-[#eef2f7]">
        <span className="block mb-2 text-[#74746f] text-xs font-bold">You</span>
        <p className="mb-0 text-sm leading-[1.65] whitespace-pre-wrap">{prompt}</p>
      </article>
      <article className="mb-5 border border-[#deded9] rounded-[5px] px-4 py-[15px] bg-[#fafaf8]">
        <span className="block mb-2 text-[#74746f] text-xs font-bold">AgentOS</span>
        <p className="text-[#74746f] text-sm leading-[1.65] mb-0">
          Working on this task…
        </p>
      </article>
    </>
  );
}

// ---------------------------------------------------------------------------
// Full conversation view
// ---------------------------------------------------------------------------

function TaskConversation({ task }: { task: TaskRecord }) {
  const isRunning = task.status === "running" || task.status === "queued";

  // The pending human message (latest follow-up not yet in messages[])
  // is the last human message in the current turn — we detect it by checking
  // if the last message is from the human and the task is still running.
  const pendingPrompt =
    isRunning &&
    task.messages.length > 0 &&
    task.messages[task.messages.length - 1].role === "human"
      ? null // already in messages[], don't double-render
      : isRunning
        ? task.title // very first turn: show title as placeholder
        : null;

  return (
    <>
      {/* Render all persisted messages */}
      {task.messages.map((msg, i) => (
        <MessageBubble key={i} message={msg} />
      ))}

      {/* If running with no messages yet, show the working placeholder */}
      {isRunning && task.messages.length === 0 && (
        <WorkingPlaceholder prompt={task.title} />
      )}

      {/* If running and the last persisted message is AI (follow-up was submitted) */}
      {pendingPrompt && task.messages.length > 0 && (
        <WorkingPlaceholder prompt={pendingPrompt} />
      )}

      {/* Error state */}
      {task.error && (
        <article className="mb-5 border border-[#deded9] rounded-[5px] px-4 py-[15px] bg-[#fff5f5]">
          <span className="block mb-2 text-[#b84343] text-xs font-bold">Error</span>
          <p className="text-[#b84343] text-sm leading-[1.65] mb-0 whitespace-pre-wrap">
            {task.error}
          </p>
        </article>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// ChatPanel
// ---------------------------------------------------------------------------

export function ChatPanel({
  selectedTask,
  isSubmitting,
  submitError,
  onSubmit,
}: ChatPanelProps) {
  return (
    <section className="grid grid-rows-[auto_1fr_auto] h-dvh min-h-screen min-w-0">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-[#deded9] px-[30px] pt-[22px] pb-[18px]">
        <div>
          <p className="m-0 mb-[3px] text-[#74746f] text-xs">Agent workspace</p>
          <h1 className="m-0 text-lg font-semibold">
            {selectedTask ? selectedTask.title : "New task"}
          </h1>
        </div>
        {selectedTask && (
          <span className="text-[#74746f] text-sm capitalize">
            {selectedTask.status}
          </span>
        )}
      </header>

      {/* Conversation area */}
      <div className="w-[min(760px,100%)] h-full mx-auto px-[30px] py-[38px] overflow-y-auto">
        {selectedTask ? (
          <TaskConversation task={selectedTask} />
        ) : (
          <EmptyConversation />
        )}
      </div>

      {/* Submit error */}
      {submitError && (
        <p className="w-[min(760px,calc(100%-60px))] mx-auto mb-2.5 text-[#b84343] text-sm">
          {submitError}
        </p>
      )}

      {/* Composer — disabled when submitting */}
      <ChatComposer
        disabled={isSubmitting}
        placeholder={
          selectedTask
            ? "Follow up on this task…"
            : "Ask AgentOS to do something…"
        }
        onSubmit={onSubmit}
      />
    </section>
  );
}
