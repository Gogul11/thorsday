"use client";

import type { DisplayEvent, TaskRecord } from "@/types";
import { formatTime } from "@/utils/time";
import { formatAgents, getAgentNames, shortId } from "@/utils/task";
import { PlanGraphModal } from "@/components/activity/PlanGraphModal";
import { useMemo, useState } from "react";

type TaskActivityProps = {
  task: TaskRecord | undefined;
};

type ActivityFilter = "all" | "scheduler" | "agents" | "tools";

/** Maps stage/status combos to timeline dot colours. */
const MARK_COLOR: Record<string, string> = {
  running: "bg-[#5e5e58]",
  started: "bg-[#5e5e58]",
  planning: "bg-[#5e5e58]",
  planned: "bg-[#5e5e58]",
  created: "bg-[#b0b0aa]",
  completed: "bg-[#242422]",
  failed: "bg-[#b84343]",
  destroyed: "bg-[#b0b0aa]",
  "tool-started": "bg-[#3b82f6]",
  "tool-completed": "bg-[#10b981]",
  "tool-failed": "bg-[#b84343]",
  page_out: "bg-[#8b5cf6]",
  page_in: "bg-[#0f766e]",
  "terminal-started": "bg-[#2563eb]",
  "terminal-completed": "bg-[#10b981]",
  "terminal-failed": "bg-[#b84343]",
  output: "bg-[#64748b]",
  ready: "bg-[#8b5cf6]",
  waiting: "bg-[#d97706]",
  preempted: "bg-[#8b5cf6]",
};

function dotColor(event: DisplayEvent): string {
  if (event.stage === "tool") {
    return MARK_COLOR[`tool-${event.status}`] ?? "bg-[#3b82f6]";
  }
  if (event.stage === "terminal") {
    return MARK_COLOR[`terminal-${event.status}`] ?? "bg-[#64748b]";
  }
  return MARK_COLOR[event.status] ?? "bg-[#b0b0aa]";
}

function formatTokens(value: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function ActivityMark({ event }: { event: DisplayEvent }) {
  return (
    <span
      aria-hidden="true"
      className={`z-10 flex-none w-2 h-2 mt-0.5 rounded-full border-2 border-white box-content ${dotColor(event)}`}
    />
  );
}

function ActivityEvent({ event }: { event: DisplayEvent }) {
  const isTool = event.stage === "tool";
  const isContext = event.stage === "context";

  return (
    <li className="grid grid-cols-[8px_minmax(0,1fr)_auto] gap-2 relative pb-[18px] last:pb-0">
      <ActivityMark event={event} />
      <div>
        <p
          className={`mb-[3px] text-xs font-bold capitalize ${
            isTool
              ? "text-[#2563eb] tracking-[0.02em] normal-case"
              : isContext
                ? "text-[#0f766e] tracking-[0.02em] normal-case"
                : ""
          }`}
        >
          {isTool ? "tool" : event.stage}
        </p>
        <p className="mb-1 text-[#74746f] text-xs leading-[1.4]">
          {event.message}
        </p>
        {event.agent_id && (
          <code
            className={`text-[10px] text-[#5a5a54] font-mono overflow-wrap-anywhere ${
              isTool
                ? "inline-block px-[5px] py-[1px] rounded-[3px] bg-[#f0f0ec] text-[#4b5563]"
                : ""
            }`}
          >
            {isTool ? `by ${event.agent_id}` : event.agent_id}
          </code>
        )}
      </div>
      <time
        dateTime={event.occurred_at}
        className="text-[#74746f] text-[10px] whitespace-nowrap"
      >
        {formatTime(event.occurred_at)}
      </time>
    </li>
  );
}

export function TaskActivity({ task }: TaskActivityProps) {
  const [showPlanGraph, setShowPlanGraph] = useState(false);
  const [copiedId, setCopiedId] = useState(false);
  const [activityFilter, setActivityFilter] = useState<ActivityFilter>("all");
  const latestEvent = task?.events.at(-1);
  const activePrompt = [...(task?.messages ?? [])].reverse().find((message) => message.role === "human")?.content ?? task?.title ?? "";
  const latestRoute = [...(task?.events ?? [])].reverse().find((event) => event.raw_event === "llm.ROUTED");
  const agents = task ? getAgentNames(task) : [];
  const visibleEvents = useMemo(() => {
    if (!task || activityFilter === "all") return task?.events ?? [];
    return task.events.filter((event) => {
      if (activityFilter === "scheduler") {
        return event.raw_event.startsWith("AGENT_") || event.raw_event.startsWith("RESOURCE_");
      }
      if (activityFilter === "agents") return event.stage === "agent";
      return event.stage === "tool";
    });
  }, [activityFilter, task]);
  const tokenUsage = task?.token_usage;
  const tokenBudget = task?.scheduler?.metrics?.resources?.token_budget;
  const visibleTokenUsage = tokenUsage ?? { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };
  const tokenPercent = tokenBudget
    ? Math.min(100, (visibleTokenUsage.total_tokens / tokenBudget) * 100)
    : 0;

  async function copyTaskId() {
    if (!task?.task_id) return;
    try {
      await navigator.clipboard.writeText(task.task_id);
      setCopiedId(true);
      window.setTimeout(() => setCopiedId(false), 1400);
    } catch {
      setCopiedId(false);
    }
  }

  return (
    <aside className="bg-white border-l border-[#deded9] px-4 py-[22px] h-dvh overflow-y-auto min-w-0">
      {/* Panel heading */}
      <div className="mt-0 mb-3 mx-0 flex items-center gap-2 text-[#74746f] text-[10px] font-bold tracking-[0.1em] uppercase">
        <span className="flex h-4 w-4 items-center justify-center rounded-full bg-[#edf4ef] text-[9px] text-[#71907d]" aria-hidden="true">
          ↯
        </span>
        <span>Task activity</span>
      </div>

      {!task ? (
        <div className="mx-0 mt-8 rounded-[10px] border border-dashed border-[#dfe4df] bg-[#fcfcfa] px-4 py-7 text-center">
          <span className="mx-auto flex h-7 w-7 items-center justify-center rounded-full bg-[#edf4ef] text-[12px] text-[#71907d]" aria-hidden="true">
            ◷
          </span>
          <p className="mt-3 text-[10px] font-semibold text-[#74746f]">Your activity will appear here</p>
          <p className="mt-1 text-[9px] leading-[1.45] text-[#a0a09a]">Select a task to follow its progress and details.</p>
        </div>
      ) : (
        <>
          {/* Task summary */}
          <div className="mx-0 mb-3 rounded-[11px] border border-[#e2e6e1] bg-white px-3 py-2.5 shadow-[0_2px_6px_rgba(30,30,28,0.03)]">
            <div className="flex items-center justify-between gap-2">
              <span
                className={`inline-flex rounded-full px-2 py-1 text-[9px] font-semibold capitalize ${
                  task.status === "completed"
                    ? "bg-[#edf7ef] text-[#317044]"
                    : task.status === "failed"
                      ? "bg-[#fff0ef] text-[#b84343]"
                      : task.status === "running"
                        ? "bg-[#f1f3f0] text-[#5e5e58]"
                        : "bg-[#f3f3f0] text-[#74746f]"
                }`}
              >
                <span className="mr-1" aria-hidden="true">•</span>
                {task.status}
              </span>
              <span className="text-[8px] font-bold uppercase tracking-[0.08em] text-[#a0a09a]">Task</span>
            </div>
            <p className="mt-3 max-h-[42px] overflow-hidden break-words text-[11px] leading-[1.4] text-[#1e1e1c]" title={activePrompt}>
              {activePrompt}
            </p>
            <div className="mt-2.5 flex items-center justify-between gap-2 border-t border-[#edf0eb] pt-2">
              <code className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap text-[9px] text-[#74746f] font-mono">
                {shortId(task.task_id || task.req_id)}
              </code>
              {task.task_id && (
                <button type="button" onClick={() => void copyTaskId()} className="flex-none text-[10px] text-[#0f766e] hover:underline">
                  {copiedId ? "Copied" : "Copy ID"}
                </button>
              )}
            </div>
          </div>

          {/* Task facts */}
          <dl className="grid gap-1.5 mx-0 mb-4">
            {task.scheduler && (
              <div className="rounded-[9px] border border-[#e2e6e1] bg-white px-2.5 py-2">
                <dt className="mb-[3px] text-[#74746f] text-[10px] font-bold tracking-[0.06em] uppercase">
                  Scheduler
                </dt>
                <dd className="m-0 text-xs leading-[1.55]">
                  <span className="font-semibold">{task.scheduler.status}</span>
                  {task.scheduler.agent_name ? ` · ${task.scheduler.agent_name}` : ""}
                  {typeof task.scheduler.effective_priority === "number" && (
                    <span className="block text-[10px] text-[#74746f]">
                      priority {task.scheduler.effective_priority.toFixed(2)}
                      {typeof task.scheduler.queue_position === "number"
                        ? ` · queue #${task.scheduler.queue_position}`
                        : ""}
                      {typeof task.scheduler.queue_wait_ms === "number"
                        ? ` · waited ${task.scheduler.queue_wait_ms} ms`
                        : ""}
                    </span>
                  )}
                  {task.scheduler.metrics?.resources && (
                    <span className="block text-[10px] text-[#74746f]">
                      slots {task.scheduler.metrics.resources.active_slots ?? 0}/
                      {task.scheduler.metrics.resources.global_slots ?? 0}
                      {typeof task.scheduler.metrics.pending === "number"
                        ? ` · ${task.scheduler.metrics.pending} queued globally`
                        : ""}
                    </span>
                  )}
                </dd>
              </div>
            )}
            {latestRoute?.provider && (
              <div className="rounded-[9px] border border-[#e2e6e1] bg-white px-2.5 py-2">
                <dt className="mb-[3px] text-[#74746f] text-[10px] font-bold tracking-[0.06em] uppercase">
                  LLM routing
                </dt>
                <dd className="m-0 text-xs leading-[1.55]">
                  <span className="font-semibold">
                    {latestRoute.provider === "ollama" ? "Ollama · local" : "Groq · cloud"}
                  </span>
                  {latestRoute.sensitive && (
                    <span className="block text-[10px] text-[#0f766e]">
                      Privacy-sensitive input stayed on this machine
                    </span>
                  )}
                  {latestRoute.operation && (
                    <span className="block text-[10px] text-[#74746f]">
                      Last operation: {latestRoute.operation}
                    </span>
                  )}
                </dd>
              </div>
            )}
            {task.scheduler && (
              <div className="rounded-[9px] border border-[#e2e6e1] bg-white px-2.5 py-2">
                <dt className="mb-[3px] text-[#74746f] text-[10px] font-bold tracking-[0.06em] uppercase">
                  Token usage
                </dt>
                <dd className="m-0 text-xs leading-[1.55]">
                  <span className="font-semibold">{formatTokens(visibleTokenUsage.total_tokens)} total</span>
                  {tokenBudget ? ` / ${formatTokens(tokenBudget)} budget` : ""}
                  <span className="block text-[10px] text-[#74746f]">
                    input {formatTokens(visibleTokenUsage.prompt_tokens)} · output {formatTokens(visibleTokenUsage.completion_tokens)}
                  </span>
                  {!tokenUsage && (
                    <span className="block text-[10px] text-[#a16207]">
                      Awaiting provider usage metadata
                      {task.scheduler.estimated_tokens
                        ? ` · estimate ${formatTokens(task.scheduler.estimated_tokens)}`
                        : ""}
                    </span>
                  )}
                  {tokenBudget && (
                    <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-[#e7eceb]" aria-label={`${tokenPercent.toFixed(1)} percent of token budget used`}>
                      <span className="block h-full rounded-full bg-[#0f766e]" style={{ width: `${tokenPercent}%` }} />
                    </span>
                  )}
                </dd>
              </div>
            )}
            <div className="rounded-[9px] border border-[#e2e6e1] bg-white px-2.5 py-2">
              <dt className="mb-[3px] text-[#74746f] text-[10px] font-bold tracking-[0.06em] uppercase">
                Current step
              </dt>
              <dd className="m-0 text-xs leading-[1.45] break-all">
                {latestEvent?.message ?? "Waiting to start."}
              </dd>
            </div>
            <div className="rounded-[9px] border border-[#e2e6e1] bg-white px-2.5 py-2">
              <dt className="mb-[3px] text-[#74746f] text-[10px] font-bold tracking-[0.06em] uppercase">
                Agents
              </dt>
              <dd className="m-0 text-xs leading-[1.45] break-all">
                {formatAgents(agents, task.status)}
              </dd>
            </div>
            <div className="rounded-[9px] border border-[#e2e6e1] bg-white px-2.5 py-2">
              <dt className="mb-[3px] text-[#74746f] text-[10px] font-bold tracking-[0.06em] uppercase">
                Activity
              </dt>
              <dd className="m-0 text-xs leading-[1.45] break-all">
                {task.events.length} events recorded
              </dd>
            </div>
            <div className="rounded-[9px] border border-[#e2e6e1] bg-white px-2.5 py-2">
              <dt className="mb-[3px] text-[#74746f] text-[10px] font-bold tracking-[0.06em] uppercase">
                Submitted
              </dt>
              <dd className="m-0 text-xs leading-[1.45] break-all">
                {formatTime(task.created_at)}
              </dd>
            </div>
          </dl>

          {/* Timeline heading */}
          <div className="mt-0 mb-1.5 mx-2 flex items-center justify-between">
            <div className="text-[#74746f] text-[10px] font-bold tracking-[0.08em] uppercase">Timeline</div>
            {task.plan_graph && (
              <button type="button" onClick={() => setShowPlanGraph(true)} className="rounded-md border border-[#c9d8d6] px-2 py-1 text-[10px] font-semibold text-[#0f766e] hover:bg-[#edf7f5]">
                View graph
              </button>
            )}
          </div>

          <div className="mx-2 mb-2 flex flex-wrap items-center gap-1" role="group" aria-label="Activity filters">
            {(["all", "scheduler", "agents", "tools"] as ActivityFilter[]).map((filter) => (
              <button
                key={filter}
                type="button"
                onClick={() => setActivityFilter(filter)}
                className={`rounded-full border px-1.5 py-0.5 text-[9px] capitalize transition-colors ${
                  activityFilter === filter
                    ? "border-[#0f766e] bg-[#edf7f5] font-semibold text-[#0f766e]"
                    : "border-[#deded9] text-[#74746f] hover:bg-[#f7f7f5]"
                }`}
              >
                {filter}
              </button>
            ))}
            {activityFilter !== "all" && (
              <span className="self-center text-[9px] text-[#a0a09a]">
                {visibleEvents.length} shown
              </span>
            )}
          </div>

          {/* Event list */}
          <ol
            className="relative grid gap-0 m-0 list-none px-2 py-0
              before:content-[''] before:absolute before:top-[5px] before:bottom-[10px] before:left-[11px] before:w-px before:bg-[#deded9]"
          >
            {visibleEvents.length === 0 ? (
              <li className="text-[#74746f] text-[11px] leading-relaxed">
                {task.events.length === 0 ? "Waiting for task activity." : "No events match this filter."}
              </li>
            ) : (
              visibleEvents.map((event, index) => (
                <ActivityEvent
                  key={`${event.occurred_at}-${index}`}
                  event={event}
                />
              ))
            )}
          </ol>
          {showPlanGraph && task.plan_graph && (
            <PlanGraphModal steps={task.plan_graph} mermaid={task.plan_mermaid} onClose={() => setShowPlanGraph(false)} />
          )}
        </>
      )}
    </aside>
  );
}
