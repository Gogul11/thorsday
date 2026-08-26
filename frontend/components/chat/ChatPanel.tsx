"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ChatComposer } from "./ChatComposer";
import type { TaskRecord } from "@/types";

type ChatPanelProps = {
  selectedTask: TaskRecord | undefined;
  isSubmitting: boolean;
  submitError: string | null;
  onSubmit: (prompt: string) => Promise<void>;
};

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

function AgentResponse({ task }: { task: TaskRecord }) {
  if (task.response) {
    return (
      <div
        className="
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
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.response}</ReactMarkdown>
      </div>
    );
  }
  if (task.error) {
    return <p className="text-[#b84343] text-sm leading-[1.65] mb-0 whitespace-pre-wrap">{task.error}</p>;
  }
  return (
    <p className="text-[#74746f] text-sm leading-[1.65] mb-0 whitespace-pre-wrap">
      Working on this task…
    </p>
  );
}

function TaskConversation({ task }: { task: TaskRecord }) {
  return (
    <>
      <article className="mb-7 border border-[#deded9] rounded-[5px] px-4 py-[15px] bg-[#eef2f7]">
        <span className="block mb-2 text-[#74746f] text-xs font-bold">You</span>
        <p className="mb-0 text-sm leading-[1.65] whitespace-pre-wrap">{task.prompt}</p>
      </article>

      <article className="mb-7 border border-[#deded9] rounded-[5px] px-4 py-[15px] bg-[#fafaf8]">
        <span className="block mb-2 text-[#74746f] text-xs font-bold">AgentOS</span>
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
    <section className="grid grid-rows-[auto_1fr_auto] h-dvh min-h-screen min-w-0">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-[#deded9] px-[30px] pt-[22px] pb-[18px]">
        <div>
          <p className="m-0 mb-[3px] text-[#74746f] text-xs">Agent workspace</p>
          <h1 className="m-0 text-lg font-semibold">
            {selectedTask ? "Task" : "New task"}
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

      <ChatComposer disabled={isSubmitting} onSubmit={onSubmit} />
    </section>
  );
}
