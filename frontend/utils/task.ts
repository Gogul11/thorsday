import type { TaskRecord } from "@/types";

/**
 * Extracts unique agent names from a task's event list.
 * Strips the task_id prefix from agent_id if present (e.g. "<task_id>-a3" → "a3").
 * Also parses planned agents from "Plan ready: ['a1', 'a3']" messages.
 */
export function getAgentNames(task: TaskRecord): string[] {
  const names = new Set<string>();

  for (const event of task.events) {
    if (event.agent_id) {
      const cleanName =
        event.agent_id.includes("-") && event.agent_id.startsWith(task.task_id)
          ? event.agent_id.slice(task.task_id.length + 1)
          : event.agent_id;
      if (cleanName && cleanName !== "agent" && cleanName !== "task") {
        names.add(cleanName);
      }
    }

    if (event.message?.startsWith("Plan ready:")) {
      const match = event.message.match(/Plan ready:\s*\[(.*?)\]/);
      if (match && match[1]) {
        match[1]
          .split(",")
          .map((s) => s.replace(/['"\s]/g, ""))
          .filter(Boolean)
          .forEach((agent) => names.add(agent));
      }
    }
  }

  return Array.from(names);
}

/**
 * Returns a formatted string describing which agents are involved in a task.
 */
export function formatAgents(agents: string[], status: string): string {
  if (agents.length > 0) {
    return agents.join(", ");
  }
  if (status === "completed") {
    return "None (Direct response)";
  }
  return "Not selected yet";
}

/**
 * Returns the first segment of a UUID-style task ID for compact display.
 * e.g. "abc123de-..." → "abc123de"
 */
export function shortId(taskId: string): string {
  return taskId.split("-")[0];
}
