import apiClient from "./client";
import type { TaskRecord } from "@/types";

// ---------------------------------------------------------------------------
// Submit a task (new or follow-up)
// ---------------------------------------------------------------------------

/**
 * POST /task
 *
 * For new tasks: omit task_id.
 * For follow-ups: pass the existing task_id.
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
 */
export async function getTask(task_id: string): Promise<TaskRecord | null> {
  try {
    const { data } = await apiClient.get<TaskRecord>(`/tasks/${task_id}`);

    return data;
  } catch {
    return null;
  }
}


// ---------------------------------------------------------------------------
// Delete confirmation
// ---------------------------------------------------------------------------

/**
 * Resolve a pending delete confirmation.
 *
 * The frontend sends only the confirmation identity.
 * The backend remains authoritative over the actual path.
 */
export async function respondToDeleteConfirmation(
  reqId: string,
  taskId: string,
  confirmationId: string,
  confirmed: boolean,
): Promise<{
  success: boolean;
  status: string;
  message?: string;
  path?: string;
}> {
  const { data } = await apiClient.post<{
    success: boolean;
    status: string;
    message?: string;
    path?: string;
  }>(
    "/delete-confirmation",
    {
      req_id: reqId,
      task_id: taskId,
      confirmation_id: confirmationId,
      confirmed,
    },
  );

  return data;
}