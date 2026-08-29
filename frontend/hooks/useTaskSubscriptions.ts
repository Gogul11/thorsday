import { useEffect, useRef } from "react";

import type { DisplayEvent, KernelEvent, TaskRecord, TaskMessage } from "@/types";
import { subscribeToTask } from "@/api/websocket";

// ---------------------------------------------------------------------------
// Kernel event → DisplayEvent
// ---------------------------------------------------------------------------

function buildMessage(ev: KernelEvent): string {
  const agent = ev.agent_name ?? ev.agent_id ?? "";
  const tool = ev.tool_name ?? "tool";

  const map: Record<string, string> = {
    "task.CREATED": "Task created.",
    "task.PLANNING": "Planning execution steps…",
    "task.PLANNED": `Plan ready: [${(ev.plan ?? []).join(", ")}]`,
    "task.COMPLETED": "Task completed.",
    "agent.STARTED": `Agent ${agent} started.`,
    "agent.COMPLETED": `Agent ${agent} completed.`,
    "agent.FAILED": `Agent ${agent} failed: ${ev.error ?? ""}`,
    "agent.DESTROYED": `Agent ${agent} destroyed.`,
    "tool.STARTED": `Tool started: ${tool}`,
    "tool.COMPLETED": `Tool completed: ${tool}`,
    "tool.FAILED": `Tool ${tool} failed: ${ev.error ?? ""}`,
  };

  return map[ev.event] ?? ev.event;
}

function stageAndStatus(eventType: string): [string, string] {
  const [prefix, suffix] = eventType.split(".");
  return [
    (prefix ?? "task").toLowerCase(),
    (suffix ?? eventType).toLowerCase(),
  ];
}

function toDisplayEvent(ev: KernelEvent): DisplayEvent {
  const [stage, status] = stageAndStatus(ev.event);
  return {
    stage,
    status,
    message: buildMessage(ev),
    occurred_at: new Date().toISOString(),
    agent_id: ev.agent_name ?? ev.agent_id ?? null,
    raw_event: ev.event,
  };
}

// ---------------------------------------------------------------------------
// Status derivation
// ---------------------------------------------------------------------------

function deriveStatus(ev: KernelEvent, current: string): string {
  if (
    ev.event === "task.CREATED" ||
    ev.event === "task.PLANNING" ||
    ev.event === "task.PLANNED"
  )
    return "running";
  if (ev.event === "task.COMPLETED") return "completed";
  if (ev.event === "agent.FAILED") return "failed";
  return current;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

const ACTIVE_STATUSES = new Set(["queued", "running"]);

/**
 * Opens one WebSocket per active in-flight request (keyed by req_id).
 *
 * When a kernel event arrives:
 * - Finds the task in state by req_id (tasks keep their current req_id while running)
 * - Merges events, status, response, plan, and task_id
 * - On task.COMPLETED, appends the AI turn to messages[]
 * - Closes the socket when the task reaches a terminal state
 */
export function useTaskSubscriptions(
  tasks: TaskRecord[],
  setTasks: React.Dispatch<React.SetStateAction<TaskRecord[]>>,
): void {
  // req_id → cleanup fn
  const subscriptions = useRef<Map<string, () => void>>(new Map());

  useEffect(() => {
    for (const task of tasks) {
      if (!ACTIVE_STATUSES.has(task.status)) continue;
      if (!task.req_id) continue;
      if (subscriptions.current.has(task.req_id)) continue;

      const cleanup = subscribeToTask(task.req_id, (ev: KernelEvent) => {
        setTasks((current) =>
          current.map((t) => {
            if (t.req_id !== task.req_id) return t;

            const displayEvent = toDisplayEvent(ev);

            // When the task completes, append the AI response to messages[]
            let updatedMessages = t.messages;
            if (ev.event === "task.COMPLETED" && ev.response) {
              const aiMsg: TaskMessage = {
                role: "ai",
                content: ev.response,
                timestamp: new Date().toISOString(),
              };
              updatedMessages = [...t.messages, aiMsg];
            }

            const updated: TaskRecord = {
              ...t,
              task_id: ev.task_id || t.task_id,
              events: [...t.events, displayEvent],
              status: deriveStatus(ev, t.status),
              response:
                ev.event === "task.COMPLETED"
                  ? (ev.response ?? t.response)
                  : t.response,
              error:
                ev.event === "agent.FAILED" || ev.event === "tool.FAILED"
                  ? (ev.error ?? t.error)
                  : t.error,
              plan: ev.event === "task.PLANNED" ? (ev.plan ?? t.plan) : t.plan,
              messages: updatedMessages,
            };

            if (
              updated.status === "completed" ||
              updated.status === "failed"
            ) {
              setTimeout(() => {
                const unsub = subscriptions.current.get(task.req_id);
                if (unsub) {
                  unsub();
                  subscriptions.current.delete(task.req_id);
                }
              }, 0);
            }

            return updated;
          }),
        );
      });

      subscriptions.current.set(task.req_id, cleanup);
    }
  }, [tasks, setTasks]);

  useEffect(() => {
    return () => {
      for (const cleanup of subscriptions.current.values()) cleanup();
      subscriptions.current.clear();
    };
  }, []);
}
