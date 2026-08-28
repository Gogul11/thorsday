import apiClient from "./client";
import type { TaskRecord } from "@/types";

// ---------------------------------------------------------------------------
// Submit a task (new or follow-up)
// ---------------------------------------------------------------------------

/**
 * POST /task
 *
 * For new tasks: omit task_id.
 * For follow-ups: pass the existing task_id — the kernel will continue
 * the same conversation thread.
 *
 * Returns req_id which is used to open the WebSocket at /ws/{req_id}.
 */
export async function createTask(
  prompt: string,
  task_id: string = "",
): Promise<{ req_id: string; status: string }> {
  const { data } = await apiClient.post<{ req_id: string; status: string }>(
    "/task",
    { prompt, task_id },
  );
  return data;
}

// ---------------------------------------------------------------------------
// Load task history (GPT-style sidebar)
// ---------------------------------------------------------------------------

/**
 * GET /tasks
 *
 * Returns all tasks newest-first with summary fields.
 * Called once on page mount to populate the sidebar.
 */
export async function getTasks(): Promise<Omit<TaskRecord, "req_id" | "events">[]> {
  const { data } = await apiClient.get<Omit<TaskRecord, "req_id" | "events">[]>(
    "/tasks",
  );
  return data;
}

/**
 * GET /tasks/{task_id}
 *
 * Returns a full task including messages[].
 * Called when the user selects a task from the sidebar.
 */
export async function getTask(task_id: string): Promise<TaskRecord | null> {
  try {
    const { data } = await apiClient.get<TaskRecord>(`/tasks/${task_id}`);
    return data;
  } catch {
    return null;
  }
}
