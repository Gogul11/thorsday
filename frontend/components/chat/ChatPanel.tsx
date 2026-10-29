"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {ChatComposer} from "./ChatComposer";
import {DeleteConfirmationDialog} from "./DeleteConfirmationDialog";

import type { TaskMessage, TaskRecord } from "@/types";

type ChatPanelProps = {
  selectedTask: TaskRecord | null;
  isSubmitting: boolean;
  submitError: string | null;
  onSubmit: (prompt: string) => Promise<void>;
  onDeleteConfirmationClose: () => void;
  // onDeleteConfirmationClose?: () => void;
};  

function EmptyConversation() {
  return (
    <div className="flex h-full items-center justify-center px-6 pb-16">
      <div className="-mt-10 w-full max-w-[620px] text-center">
        <div className="text-[31px] font-bold tracking-[-0.06em] text-[#1e1e1c]">
          Agent<span className="font-normal text-[#74746f]">OS</span>
        </div>
        <div className="mt-1 text-[9px] font-bold uppercase tracking-[0.28em] text-[#a0a09a]">
          Your AI workspace
        </div>

        <h2 className="mt-7 text-[25px] font-semibold leading-[1.08] tracking-[-0.035em] text-[#1e1e1c]">
          What can I help you
          <br />
          get done today?
        </h2>

        <p className="mx-auto mt-3 max-w-[430px] text-[11px] leading-[1.55] text-[#74746f]">
          Give AgentOS a goal, it can plan the work, use the right tools, and keep
          you updated along the way.
        </p>

        <div className="mx-auto mt-9 grid max-w-[510px] grid-cols-3 gap-2 text-left">
          {[
            ["01", "Research", "Compare options and bring back a clear summary."],
            ["02", "Analyze", "Turn files and information into useful insights."],
            ["03", "Create", "Draft a plan, a document, or your next idea."],
          ].map(([number, title, description]) => (
            <div
              key={number}
              className="min-h-[99px] rounded-[9px] border border-[#e2e2dd] bg-white p-3 shadow-[0_1px_2px_rgba(30,30,28,0.02)]"
            >
              <span className="inline-flex rounded-[5px] bg-[#edf4ef] px-1.5 py-1 text-[9px] font-semibold text-[#5f806d]">
                {number}
              </span>
              <h3 className="mt-2 text-[11px] font-semibold text-[#1e1e1c]">{title}</h3>
              <p className="mt-1 text-[9px] leading-[1.45] text-[#74746f]">{description}</p>
            </div>
          ))}
        </div>

        <p className="mt-4 text-[9px] text-[#a0a09a]">
          Start by describing what you need in the box below.
        </p>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: TaskMessage }) {
  const isHuman = message.role === "human";

  return (
    <div
      className={`flex w-full ${
        isHuman ? "justify-end" : "justify-start"
      }`}
    >
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
          isHuman
            ? "bg-black text-white"
            : "bg-gray-100 text-gray-900"
        }`}
      >
        {isHuman ? (
          <div className="whitespace-pre-wrap">{message.content}</div>
        ) : (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

function WorkingPlaceholder() {
  return (
    <div className="flex justify-start">
      <div className="rounded-2xl bg-gray-100 px-4 py-3 text-sm text-gray-500">
        <div className="flex items-center gap-2">
          <span>Working</span>

          <span className="flex gap-1">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" />
          </span>
        </div>
      </div>
    </div>
  );
}

function TaskConversation({ task }: { task: TaskRecord }) {
  const isRunning =
    task.status === "running" || task.status === "queued";

  const messages = task.messages ?? [];

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto flex max-w-4xl flex-col gap-4">
          {messages.map((message, index) => (
            <MessageBubble
              key={`${task.task_id}-${message.timestamp}-${index}`}
              message={message}
            />
          ))}

          {isRunning && <WorkingPlaceholder />}

          {!isRunning && task.error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {task.error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ChatPanel({
  selectedTask,
  isSubmitting,
  submitError,
  onSubmit,
  onDeleteConfirmationClose,
}: ChatPanelProps) {
  const confirmation = selectedTask?.delete_confirmation ?? null;

  return (
    <div className="relative flex h-full min-h-0 flex-col bg-white">
      {/* Conversation */}
      <div className="min-h-0 flex-1">
        {selectedTask ? (
          <TaskConversation task={selectedTask} />
        ) : (
          <EmptyConversation />
        )}
      </div>

      {/* Submit error */}
      {submitError && (
        <div className="px-6 pb-2">
          <div className="mx-auto max-w-4xl rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
            {submitError}
          </div>
        </div>
      )}

      {/* Composer */}
      <div className="shrink-0 border-t border-gray-200 bg-white px-6 py-4">
        <div className="mx-auto max-w-4xl">
          <ChatComposer
            disabled={isSubmitting}
            onSubmit={onSubmit}
          />
        </div>
      </div>

      {/* Delete confirmation */}
      {confirmation && (
        <DeleteConfirmationDialog
          confirmation={confirmation}
          onClose={onDeleteConfirmationClose}
        />
      )}
    </div>
  );
}
