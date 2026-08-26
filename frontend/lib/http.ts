import type { TaskStatus } from "./types";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function createTask(prompt: string): Promise<{
  task_id: string;
  status: string;
}> {
  return request("/task", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

export function getTaskStatus(taskId: string): Promise<TaskStatus> {
  return request(`/status/${taskId}`);
}
