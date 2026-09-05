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
    | "DELETE_CONFIRMATION_REQUIRED"
    | string;

  req_id: string;
  task_id: string;

  // task.PLANNED
  plan?: string[];

  // agent.* / tool.*
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

  // DELETE_CONFIRMATION_REQUIRED
  confirmation_id?: string;
  path?: string;
  recursive?: boolean;
};


// ---------------------------------------------------------------------------
// Delete confirmation — pending destructive operation
// ---------------------------------------------------------------------------

export type DeleteConfirmation = {
  reqId: string;
  taskId: string;
  confirmationId: string;
  path: string;
  recursive: boolean;
};


// ---------------------------------------------------------------------------
// Derived display event — synthesised from a KernelEvent for the timeline UI
// ---------------------------------------------------------------------------

export type DisplayEvent = {
  /** "task" | "agent" | "tool" | "delete" */
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
// Conversation message — one turn in the task history
// ---------------------------------------------------------------------------

export type TaskMessage = {
  /** "human" | "ai" */
  role: "human" | "ai";
  content: string;
  timestamp: string;
};


// ---------------------------------------------------------------------------
// Task record — client-side state for one task
// ---------------------------------------------------------------------------

/**
 * Everything the frontend knows about a task.
 *
 * Keyed by `task_id` (the kernel's persistent ID).
 * `req_id` is the transient WebSocket key for the current in-flight request.
 */
export type TaskRecord = {
  /** Kernel-assigned persistent ID — primary key */
  task_id: string;

  /** Transient request ID for the current WS connection */
  req_id: string;

  /** Display title — first prompt, truncated */
  title: string;

  /** ISO timestamp of creation */
  created_at: string;

  /** "queued" | "running" | "completed" | "failed" */
  status: string;

  /** Full conversation history */
  messages: TaskMessage[];

  /** Final markdown response */
  response: string | null;

  /** Error string if the task failed */
  error: string | null;

  /** Ordered list of display-ready events */
  events: DisplayEvent[];

  /** Agents selected by the planner */
  plan: string[];

  /** Pending destructive operation */
  delete_confirmation?: {
    reqId: string;
    taskId: string;
    confirmationId: string;
    path: string;
    recursive: boolean;
  } | null;
};