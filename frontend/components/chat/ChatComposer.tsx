"use client";

import { FormEvent, KeyboardEvent, useState } from "react";

type ChatComposerProps = {
  disabled: boolean;
  onSubmit: (prompt: string) => Promise<void>;
};

export function ChatComposer({ disabled, onSubmit }: ChatComposerProps) {
  const [prompt, setPrompt] = useState("");

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const nextPrompt = prompt.trim();

    if (!nextPrompt || disabled) {
      return;
    }

    await onSubmit(nextPrompt);
    setPrompt("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      void submit();
    }
  }

  return (
    <form
      className="w-[min(760px,calc(100%-60px))] mx-auto mb-7 border border-[#deded9] rounded-md bg-white"
      onSubmit={submit}
    >
      <textarea
        aria-label="Task prompt"
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask AgentOS to do something..."
        rows={3}
        disabled={disabled}
        className="block w-full resize-y border-0 outline-none rounded-t-md px-3.5 pt-3 pb-2 bg-transparent text-[#1e1e1c] text-sm leading-[1.45] disabled:cursor-not-allowed"
      />
      <div className="flex items-center justify-between px-3 pt-2 pb-2.5 text-[#74746f] text-[11px]">
        <span>Ctrl + Enter to send</span>
        <button
          type="submit"
          disabled={disabled || !prompt.trim()}
          className="border border-[#292927] rounded bg-[#292927] px-2.5 py-1.5 text-white text-xs hover:bg-[#3b3b37] disabled:border-[#deded9] disabled:bg-[#f0f0ec] disabled:text-[#74746f] disabled:cursor-not-allowed"
        >
          {disabled ? "Sending..." : "Send task"}
        </button>
      </div>
    </form>
  );
}
