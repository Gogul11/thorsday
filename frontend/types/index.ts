// ---------------------------------------------------------------------------
// Raw kernel events — shape of every WS message pushed by the backend
// ---------------------------------------------------------------------------

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
};

// ---------------------------------------------------------------------------
// Derived display event — synthesised from a KernelEvent for the timeline UI
// ---------------------------------------------------------------------------

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
// Conversation message — one turn in the task history
// ---------------------------------------------------------------------------

export type TaskMessage = {
  /** "human" | "ai" */
  role: "human" | "ai";
  content: string;
  /** ISO timestamp */
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
  /** Transient request ID for the current WS connection (changes each follow-up) */
  req_id: string;
  /** Display title — first prompt, truncated */
  title: string;
  /** ISO timestamp of creation */
  created_at: string;
  /** "queued" | "running" | "completed" | "failed" */
  status: string;
  /** Full conversation history: all human + ai turns */
  messages: TaskMessage[];
  /** Final markdown response from the last completed turn */
  response: string | null;
  /** Error string if the task failed */
  error: string | null;
  /** Ordered list of display-ready events */
  events: DisplayEvent[];
  /** Agents selected by the planner (task.PLANNED) */
  plan: string[];
};
