import type { TaskRecord } from "@/types";

/**
 * Returns the list of agent names involved in a task.
 *
 * Primary source: `task.plan` (captured from the kernel's task.PLANNED event).
 * Fallback: unique agent_id values from agent.* DisplayEvents.
 */
export function getAgentNames(task: TaskRecord): string[] {
  // Prefer the planner's explicit list
  if (task.plan.length > 0) {
    return task.plan;
  }

  // Fallback: collect agent_id from agent-stage display events
  const names = new Set<string>();
  for (const ev of task.events) {
    if (ev.stage === "agent" && ev.agent_id) {
      names.add(ev.agent_id);
    }
  }
  return Array.from(names);
}

/**
 * Returns a formatted string describing which agents are involved in a task.
 */
export function formatAgents(agents: string[], status: string): string {
  if (agents.length > 0) return agents.join(", ");
  if (status === "completed") return "None (direct response)";
  return "Not selected yet";
}

/**
 * Returns the first segment of a UUID-style ID for compact display.
 * e.g. "abc123de-…" → "abc123de"
 */
export function shortId(id: string): string {
  return id.split("-")[0];
}
