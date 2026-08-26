/** A single timestamped event emitted by the kernel for a task. */
export type TaskEvent = {
  stage: string;
  status: string;
  message: string;
  occurred_at: string;
  agent_id: string | null;
};

/** The full status snapshot returned by GET /status/:task_id. */
export type TaskStatus = {
  task_id: string;
  status: string;
  response: string | null;
  error: string | null;
  events: TaskEvent[];
};

/**
 * Client-side task record: TaskStatus extended with the original prompt and
 * the local submission timestamp.
 */
export type TaskRecord = TaskStatus & {
  prompt: string;
  submittedAt: string;
};

/** Shape of every message pushed by the backend over the WebSocket. */
export type KernelMessage = {
  event: string;
  req_id: string;
  task_id: string;
  latest_event: TaskEvent;
  status: string | null;
  response: string | null;
  error: string | null;
};
