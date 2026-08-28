import { useEffect, useRef } from "react";

import type { DisplayEvent, KernelEvent, TaskRecord } from "@/types";
import { subscribeToTask } from "@/api/websocket";

// ---------------------------------------------------------------------------
// Kernel event → DisplayEvent translation
// ---------------------------------------------------------------------------

/** Maps a raw kernel event to a human-readable message. */
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

/** Derive [stage, status] from the raw event string. */
function stageAndStatus(eventType: string): [string, string] {
  const [prefix, suffix] = eventType.split(".");
  return [
    (prefix ?? "task").toLowerCase(),
    (suffix ?? eventType).toLowerCase(),
  ];
}

/** Convert a raw KernelEvent to a DisplayEvent ready for the timeline. */
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
// Status / response / plan derivation
// ---------------------------------------------------------------------------

function deriveStatus(ev: KernelEvent, current: string): string {
  if (ev.event === "task.CREATED" || ev.event === "task.PLANNING" || ev.event === "task.PLANNED")
    return "running";
  if (ev.event === "task.COMPLETED") return "completed";
  if (ev.event === "agent.FAILED") return "failed";
  return current;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/** Task statuses that can still receive kernel events. */
const ACTIVE_STATUSES = new Set(["queued", "running"]);

/**
 * Opens one WebSocket per active task (keyed by req_id) and merges incoming
 * kernel events into the shared `tasks` state.
 *
 * - Subscribes as soon as a task appears with an active status.
 * - Translates raw KernelEvents to DisplayEvents for the timeline.
 * - Derives `status`, `response`, `error`, `task_id`, and `plan` from events.
 * - Closes the socket when the task reaches a terminal state or on unmount.
 */
export function useTaskSubscriptions(
  tasks: TaskRecord[],
  setTasks: React.Dispatch<React.SetStateAction<TaskRecord[]>>,
): void {
  // req_id → cleanup fn — held in a ref so it outlives re-renders
  const subscriptions = useRef<Map<string, () => void>>(new Map());

  useEffect(() => {
    for (const task of tasks) {
      if (!ACTIVE_STATUSES.has(task.status)) continue;
      if (subscriptions.current.has(task.req_id)) continue;

      const cleanup = subscribeToTask(task.req_id, (ev: KernelEvent) => {
        setTasks((current) =>
          current.map((t) => {
            if (t.req_id !== task.req_id) return t;

            const displayEvent = toDisplayEvent(ev);

            // Build updated task record
            const updated: TaskRecord = {
              ...t,
              // Capture the kernel-assigned task_id as soon as it arrives
              task_id: ev.task_id || t.task_id,
              events: [...t.events, displayEvent],
              status: deriveStatus(ev, t.status),
              response: ev.event === "task.COMPLETED" ? (ev.response ?? t.response) : t.response,
              error: (ev.event === "agent.FAILED" || ev.event === "tool.FAILED")
                ? (ev.error ?? t.error)
                : t.error,
              // Capture plan from task.PLANNED
              plan: ev.event === "task.PLANNED" ? (ev.plan ?? t.plan) : t.plan,
            };

            // Close the socket once the task is terminal
            if (updated.status === "completed" || updated.status === "failed") {
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

  // Tear down every open socket on unmount
  useEffect(() => {
    return () => {
      for (const cleanup of subscriptions.current.values()) cleanup();
      subscriptions.current.clear();
    };
  }, []);
}
