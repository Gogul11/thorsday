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
};  

function EmptyConversation() {
  return (
    <div className="flex h-full items-center justify-center px-6">
      <div className="max-w-md text-center">
        <h2 className="text-lg font-semibold text-gray-900">
          Start a conversation
        </h2>

        <p className="mt-2 text-sm text-gray-500">
          Ask the agent to research, analyze, create files, or perform a task.
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