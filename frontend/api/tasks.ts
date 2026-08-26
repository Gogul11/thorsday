import type { TaskStatus } from "@/types";
import apiClient from "./client";

/**
 * Creates a new task on the backend.
 * POST /task
 */
export async function createTask(prompt: string): Promise<{
  task_id: string;
  status: string;
}> {
  const { data } = await apiClient.post<{ task_id: string; status: string }>(
    "/task",
    { prompt },
  );
  return data;
}

/**
 * Fetches the current status of a task.
 * GET /status/:taskId
 */
export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const { data } = await apiClient.get<TaskStatus>(`/status/${taskId}`);
  return data;
}
