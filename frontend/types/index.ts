// ---------------------------------------------------------------------------
// Raw kernel events — shape of every WS message pushed by the backend
// ---------------------------------------------------------------------------

/**
 * Every message the backend pushes over the WebSocket is a raw kernel event.
 * The `event` field tells you what happened; additional fields are
 * event-specific.
 */
export type KernelEvent = {
  event:
    | "task.CREATED"
    | "task.PLANNING"
    | "task.PLANNED"
    | "task.COMPLETED"
    | "agent.STARTED"
    | "agent.COMPLETED"
    | "agent.FAILED"
    | "agent.DESTROYED"
    | "tool.STARTED"
    | "tool.COMPLETED"
    | "tool.FAILED"
    | string; // future events

  req_id: string;
  task_id: string;

  // task.PLANNED
  plan?: string[];

  // agent.*  /  tool.*
  agent_id?: string;
  agent_name?: string;

  // tool.*
  tool_name?: string;
  tool_input?: string;

  // agent.COMPLETED
  result?: string;

  // task.COMPLETED
  response?: string;

  // *.FAILED
  error?: string;
};

// ---------------------------------------------------------------------------
// Derived display event — synthesised from a KernelEvent for the timeline UI
// ---------------------------------------------------------------------------

/**
 * A normalised, display-ready event synthesised from a raw KernelEvent.
 * Components should render these instead of raw events directly.
 */
export type DisplayEvent = {
  /** "task" | "agent" | "tool" */
  stage: string;
  /** e.g. "created", "started", "failed" */
  status: string;
  /** Human-readable description */
  message: string;
  /** ISO timestamp — set to Date.now() when the event is received */
  occurred_at: string;
  /** Agent identifier, if relevant */
  agent_id: string | null;
  /** Original raw event type for programmatic checks */
  raw_event: string;
};

// ---------------------------------------------------------------------------
// Task record — client-side state for one submitted task
// ---------------------------------------------------------------------------

/**
 * Everything the frontend knows about a task.
 *
 * Keyed by `req_id` (returned by POST /task).
 * `task_id` arrives later via the first WS event from the kernel.
 */
export type TaskRecord = {
  /** Returned immediately by POST /task — also the WS subscription key */
  req_id: string;
  /** Assigned by the kernel on task.CREATED — may be "" until that event */
  task_id: string;
  /** Original prompt submitted by the user */
  prompt: string;
  /** ISO timestamp of local submission */
  submittedAt: string;
  /** "queued" | "running" | "completed" | "failed" */
  status: string;
  /** Final markdown response from the kernel (task.COMPLETED) */
  response: string | null;
  /** Error string if the task failed */
  error: string | null;
  /** Ordered list of display-ready events */
  events: DisplayEvent[];
  /** Agents selected by the planner (task.PLANNED) */
  plan: string[];
};
