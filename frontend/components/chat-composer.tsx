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
    <form className="composer" onSubmit={submit}>
      <textarea
        aria-label="Task prompt"
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask AgentOS to do something..."
        rows={3}
        disabled={disabled}
      />
      <div className="composer-footer">
        <span>Ctrl + Enter to send</span>
        <button type="submit" disabled={disabled || !prompt.trim()}>
          {disabled ? "Sending..." : "Send task"}
        </button>
      </div>
    </form>
  );
}
