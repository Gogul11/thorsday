import apiClient from "./client";

/**
 * Submit a new task.
 * POST /task
 *
 * Returns the req_id which is used to:
 *   1. Key the task in local state
 *   2. Open the WebSocket at /ws/{req_id}
 */
export async function createTask(prompt: string): Promise<{
  req_id: string;
  status: string;
}> {
  const { data } = await apiClient.post<{ req_id: string; status: string }>(
    "/task",
    { prompt },
  );
  return data;
}
