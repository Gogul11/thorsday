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
    | "AGENT_READY"
    | "AGENT_RUNNING"
    | "AGENT_WAITING"
    | "AGENT_BLOCKED"
    | "AGENT_COMPLETED"
    | "AGENT_FAILED"
    | "AGENT_PREEMPTED"
    | "RESOURCE_APPROVED"
    | "RESOURCE_DENIED"
    | "tool.STARTED"
    | "tool.COMPLETED"
    | "tool.FAILED"
    | "DELETE_CONFIRMATION_REQUIRED"
    | string;

  req_id: string;
  task_id: string;

  // task.PLANNED
  plan?: string[];
  candidates?: string[];
  confidence?: number;
  rationale?: string;
  plan_graph?: PlanStep[];
  mermaid?: string;

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

  // Context paging
  paged_count?: number;
  total_in_swap?: number;
  pages_injected?: number;
  top_similarity?: number;

  // DELETE_CONFIRMATION_REQUIRED
  confirmation_id?: string;
  path?: string;
  recursive?: boolean;

  // terminal.* code-runner events
  stream?: "stdout" | "stderr";
  line?: string;
  exit_code?: number;
  duration_ms?: number;
  timeout_seconds?: number;
  timed_out?: boolean;
  truncated?: boolean;
  attempt?: number;

  // Global scheduler
  step_id?: string;
  execution_id?: string;
  status?: string;
  priority?: number;
  effective_priority?: number;
  queue_wait_ms?: number;
  queue_position?: number;
  time_quantum?: number;
  reason?: string;
  timestamp?: number;
  scheduler_metrics?: SchedulerMetrics;
  token_usage?: TokenUsage;
};

export type PlanStep = {
  id: string;
  agent: string;
  depends_on: string[];
  purpose: string;
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
  plan_graph?: PlanStep[];
  plan_mermaid?: string;
  token_usage?: TokenUsage;

  scheduler?: SchedulerSnapshot;

  /** Pending destructive operation */
  delete_confirmation?: {
    reqId: string;
    taskId: string;
    confirmationId: string;
    path: string;
    recursive: boolean;
  } | null;
};

export type SchedulerSnapshot = {
  status: string;
  agent_name?: string;
  step_id?: string;
  priority?: number;
  effective_priority?: number;
  queue_position?: number;
  queue_wait_ms?: number;
  attempt?: number;
  execution_id?: string;
  metrics?: SchedulerMetrics;
  token_usage?: TokenUsage;
};

export type TokenUsage = {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
};

export type SchedulerMetrics = {
  pending?: number;
  metrics?: {
    submitted?: number;
    completed?: number;
    failed?: number;
    requeued?: number;
    wait_ms?: number;
  };
  resources?: {
    global_slots?: number;
    active_slots?: number;
    task_slots?: number;
    token_budget?: number;
  };
};
