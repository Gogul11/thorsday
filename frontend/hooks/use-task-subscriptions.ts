import { useEffect, useRef } from "react";

import type { KernelMessage, TaskRecord } from "@/lib/types";
import { subscribeToTask } from "@/lib/ws";

/** Task statuses that can still receive kernel events. */
const ACTIVE_STATUSES = new Set(["queued", "running"]);

/**
 * Opens one WebSocket per active task and merges incoming kernel messages
 * into the shared `tasks` state via `setTasks`.
 *
 * Subscription lifecycle:
 * - A socket is opened the first time a task appears with an active status.
 * - The socket is closed as soon as the backend sends a terminal status
 *   ("completed" | "failed"), or when the component unmounts.
 */
export function useTaskSubscriptions(
  tasks: TaskRecord[],
  setTasks: React.Dispatch<React.SetStateAction<TaskRecord[]>>,
): void {
  // Map of task_id → cleanup function.  Held in a ref so it survives
  // re-renders without triggering new effects.
  const subscriptions = useRef<Map<string, () => void>>(new Map());

  useEffect(() => {
    for (const task of tasks) {
      if (!ACTIVE_STATUSES.has(task.status)) continue;
      if (subscriptions.current.has(task.task_id)) continue;

      const cleanup = subscribeToTask(task.task_id, (msg: KernelMessage) => {
        setTasks((current) =>
          current.map((t) => {
            if (t.task_id !== task.task_id) return t;

            // Deduplicate: skip if we already have this exact event
            const alreadyExists = t.events.some(
              (e) =>
                e.occurred_at === msg.latest_event.occurred_at &&
                e.message === msg.latest_event.message,
            );

            const updatedTask: TaskRecord = {
              ...t,
              events: alreadyExists
                ? t.events
                : [...t.events, msg.latest_event],
              status: msg.status ?? t.status,
              response: msg.response ?? t.response,
              error: msg.error ?? t.error,
            };

            // Unsubscribe once the task reaches a terminal state
            if (msg.status === "completed" || msg.status === "failed") {
              setTimeout(() => {
                const unsub = subscriptions.current.get(task.task_id);
                if (unsub) {
                  unsub();
                  subscriptions.current.delete(task.task_id);
                }
              }, 0);
            }

            return updatedTask;
          }),
        );
      });

      subscriptions.current.set(task.task_id, cleanup);
    }
  }, [tasks, setTasks]);

  // Tear down every open socket on unmount
  useEffect(() => {
    return () => {
      for (const cleanup of subscriptions.current.values()) {
        cleanup();
      }
      subscriptions.current.clear();
    };
  }, []);
}
