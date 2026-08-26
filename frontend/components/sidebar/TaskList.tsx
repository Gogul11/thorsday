import type { TaskRecord } from "@/types";
import { shortId } from "@/utils/task";

type TaskListProps = {
  tasks: TaskRecord[];
  selectedTaskId: string | null;
  onSelect: (taskId: string) => void;
  onNewTask: () => void;
  collapsed: boolean;
  onToggle: () => void;
};

/** Maps task status to a dot colour class. */
const STATUS_DOT_COLOR: Record<string, string> = {
  running: "bg-[#5e5e58]",
  completed: "bg-[#242422]",
  failed: "bg-[#b84343]",
};

function StatusDot({ status }: { status: string }) {
  const color = STATUS_DOT_COLOR[status] ?? "bg-[#b0b0aa]";
  return (
    <span
      aria-hidden="true"
      className={`flex-none w-2 h-2 mt-[5px] rounded-full ${color}`}
    />
  );
}

export function TaskList({
  tasks,
  selectedTaskId,
  onSelect,
  onNewTask,
  collapsed,
  onToggle,
}: TaskListProps) {
  return (
    <aside
      className={`bg-white border-r border-[#deded9] h-dvh overflow-y-auto overflow-x-hidden min-w-0 ${
        collapsed ? "px-3 py-[22px]" : "px-4 py-[22px]"
      }`}
    >
      {/* Header */}
      <div
        className={`flex items-center justify-between mb-[22px] ${
          collapsed ? "mx-0.5" : "mx-2"
        }`}
      >
        <span className="text-[17px] font-bold tracking-[-0.02em]">
          {collapsed ? "A" : "AgentOS"}
        </span>
        <button
          className="border-0 bg-transparent text-[#74746f] px-1 py-0.5 text-sm hover:text-[#1e1e1c]"
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? "Expand task sidebar" : "Collapse task sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>

      {/* New task button */}
      <button
        className={`w-full border border-[#292927] bg-[#292927] text-white rounded-[5px] text-sm hover:bg-[#3b3b37] ${
          collapsed ? "py-2 px-0 text-center" : "py-2 px-2.5 text-left"
        }`}
        type="button"
        onClick={onNewTask}
        aria-label="Create a new task"
        title="Create a new task"
      >
        {collapsed ? "+" : "+ New task"}
      </button>

      {/* Section heading */}
      {!collapsed && (
        <div className="mt-7 mb-2.5 mx-2 text-[#74746f] text-[11px] font-bold tracking-[0.08em] uppercase">
          Tasks
        </div>
      )}

      {/* Task list */}
      <div className="grid gap-[3px] min-w-0">
        {tasks.length === 0 ? (
          !collapsed ? (
            <p className="mx-2 text-[#74746f] text-xs leading-relaxed">
              Tasks you send will appear here.
            </p>
          ) : null
        ) : (
          tasks.map((task) => (
            <button
              key={task.task_id}
              type="button"
              onClick={() => onSelect(task.task_id)}
              aria-label={task.prompt}
              title={task.prompt}
              className={`flex gap-2 w-full border-0 rounded-[5px] bg-transparent text-[#1e1e1c] text-left min-w-0 overflow-hidden hover:bg-[#f0f0ec] ${
                task.task_id === selectedTaskId ? "bg-[#f0f0ec]" : ""
              } ${collapsed ? "justify-center py-2 px-0" : "p-2"}`}
            >
              <StatusDot status={task.status} />
              {!collapsed && (
                <span className="min-w-0">
                  <span className="block text-[13px] leading-[1.35] overflow-hidden text-ellipsis whitespace-nowrap">
                    {task.prompt}
                  </span>
                  <span className="block mt-[3px] text-[#74746f] text-[11px] overflow-hidden text-ellipsis whitespace-nowrap">
                    {shortId(task.task_id)} · {task.status}
                  </span>
                </span>
              )}
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
