import { useEffect, useRef } from "react";

import type {
  DisplayEvent,
  KernelEvent,
  TaskRecord,
  TaskMessage,
} from "@/types";

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

    "DELETE_CONFIRMATION_REQUIRED":
      "Waiting for confirmation before deleting the file.",
    "DELETE_COMPLETED":
      "File deletion completed.",
    "DELETE_CANCELLED":
      "File deletion cancelled.",
    "DELETE_FAILED":
      `File deletion failed: ${ev.error ?? ""}`,
  };

  if (ev.event === "DELETE_CONFIRMATION_REQUIRED") {
    return `Delete confirmation required for ${ev.path ?? "the requested path"}.`;
  }

  return map[ev.event] ?? ev.event;
}

// ---------------------------------------------------------------------------
// Event → display stage/status
// ---------------------------------------------------------------------------

function stageAndStatus(eventType: string): [string, string] {
  const [prefix, suffix] = eventType.split(".");

  return [
    (prefix ?? "task").toLowerCase(),
    (suffix ?? eventType).toLowerCase(),
  ];
}

// ---------------------------------------------------------------------------
// Kernel event → DisplayEvent
// ---------------------------------------------------------------------------

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

function deriveStatus(
  ev: KernelEvent,
  current: string,
): string {
  if (
    ev.event === "task.CREATED" ||
    ev.event === "task.PLANNING" ||
    ev.event === "task.PLANNED"
  ) {
    return "running";
  }

  if (ev.event === "task.COMPLETED") {
    return "completed";
  }

  if (ev.event === "agent.FAILED") {
    return "failed";
  }

  return current;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

const ACTIVE_STATUSES = new Set([
  "queued",
  "running",
]);

export function useTaskSubscriptions(
  tasks: TaskRecord[],
  setTasks: React.Dispatch<
    React.SetStateAction<TaskRecord[]>
  >,
): void {
  const subscriptions = useRef<
    Map<string, () => void>
  >(new Map());

  useEffect(() => {
    for (const task of tasks) {
      if (!ACTIVE_STATUSES.has(task.status)) {
        continue;
      }

      if (!task.req_id) {
        continue;
      }

      if (subscriptions.current.has(task.req_id)) {
        continue;
      }

      const cleanup = subscribeToTask(
        task.req_id,
        (ev: KernelEvent) => {
          setTasks((current) =>
            current.map((t) => {
              if (t.req_id !== task.req_id) {
                return t;
              }

              const displayEvent = toDisplayEvent(ev);

              // -----------------------------------------------------------
              // Messages
              // -----------------------------------------------------------

              let updatedMessages = t.messages;

              if (
                ev.event === "task.COMPLETED" &&
                ev.response
              ) {
                const aiMsg: TaskMessage = {
                  role: "ai",
                  content: ev.response,
                  timestamp: new Date().toISOString(),
                };

                updatedMessages = [
                  ...t.messages,
                  aiMsg,
                ];
              }

              // -----------------------------------------------------------
              // DELETE CONFIRMATION
              //
              // IMPORTANT:
              // Once received, preserve this object across subsequent
              // WebSocket events until the user resolves it.
              // -----------------------------------------------------------

              let delete_confirmation =
                t.delete_confirmation ?? null;

              if (
                ev.event ===
                "DELETE_CONFIRMATION_REQUIRED"
              ) {
                delete_confirmation = {
                  reqId: ev.req_id,
                  taskId:
                    ev.task_id || t.task_id,
                  confirmationId:
                    ev.confirmation_id ?? "",
                  path: ev.path ?? "",
                  recursive:
                    ev.recursive ?? false,
                };
              }

              // -----------------------------------------------------------
              // IMPORTANT:
              //
              // Do NOT clear delete_confirmation merely because another
              // kernel event arrived.
              //
              // It must remain visible until DeleteConfirmationDialog
              // resolves it.
              // -----------------------------------------------------------

              const updated: TaskRecord = {
                ...t,

                task_id:
                  ev.task_id || t.task_id,

                events: [
                  ...t.events,
                  displayEvent,
                ],

                status: deriveStatus(
                  ev,
                  t.status,
                ),

                response:
                  ev.event === "task.COMPLETED"
                    ? (
                        ev.response ??
                        t.response
                      )
                    : t.response,

                error:
                  ev.event === "agent.FAILED" ||
                  ev.event === "tool.FAILED"
                    ? (
                        ev.error ??
                        t.error
                      )
                    : t.error,

                plan:
                  ev.event === "task.PLANNED"
                    ? (
                        ev.plan ??
                        t.plan
                      )
                    : t.plan,

                messages: updatedMessages,

                // THIS IS THE IMPORTANT PART
                delete_confirmation:
                  ev.event === "DELETE_CONFIRMATION_REQUIRED"
                    ? {
                        reqId: ev.req_id,
                        taskId: ev.task_id || t.task_id,
                        confirmationId: ev.confirmation_id ?? "",
                        path: ev.path ?? "",
                        recursive: ev.recursive ?? false,
                      }
                    : ev.event === "DELETE_COMPLETED" ||
                        ev.event === "DELETE_CANCELLED" ||
                        ev.event === "DELETE_FAILED"
                      ? null
                      : t.delete_confirmation,
              };

              // -----------------------------------------------------------
              // Do NOT close the WebSocket when the task is waiting for
              // delete confirmation.
              // -----------------------------------------------------------

              if (
                updated.status === "completed" ||
                updated.status === "failed"
              ) {
                setTimeout(() => {
                  const unsub =
                    subscriptions.current.get(
                      task.req_id,
                    );

                  if (unsub) {
                    unsub();

                    subscriptions.current.delete(
                      task.req_id,
                    );
                  }
                }, 0);
              }

              return updated;
            }),
          );
        },
      );

      subscriptions.current.set(
        task.req_id,
        cleanup,
      );
    }

    return undefined;
  }, [tasks, setTasks]);

  useEffect(() => {
    return () => {
      for (
        const cleanup
        of subscriptions.current.values()
      ) {
        cleanup();
      }

      subscriptions.current.clear();
    };
  }, []);
}