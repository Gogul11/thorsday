import { TaskStatus } from "@/lib/api";

export type TaskRecord = TaskStatus & {
  prompt: string;
  submittedAt: string;
};

type TaskListProps = {
  tasks: TaskRecord[];
  selectedTaskId: string | null;
  onSelect: (taskId: string) => void;
  onNewTask: () => void;
  collapsed: boolean;
  onToggle: () => void;
};

function shortId(taskId: string) {
  return taskId.split("-")[0];
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
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-top">
        <div className="product-name">{collapsed ? "A" : "AgentOS"}</div>
        <button
          className="sidebar-toggle"
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? "Expand task sidebar" : "Collapse task sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? ">" : "<"}
        </button>
      </div>
      <button
        className="new-task-button"
        type="button"
        onClick={onNewTask}
        aria-label="Create a new task"
        title="Create a new task"
      >
        {collapsed ? "+" : "+ New task"}
      </button>

      {!collapsed ? <div className="sidebar-heading">Tasks</div> : null}
      <div className="task-list">
        {tasks.length === 0 ? (
          !collapsed ? <p className="empty-sidebar">Tasks you send will appear here.</p> : null
        ) : (
          tasks.map((task) => (
            <button
              className={`task-item ${task.task_id === selectedTaskId ? "selected" : ""}`}
              key={task.task_id}
              type="button"
              onClick={() => onSelect(task.task_id)}
              aria-label={task.prompt}
              title={task.prompt}
            >
              <span className={`status-dot ${task.status}`} aria-hidden="true" />
              <span className="task-item-content">
                <span className="task-item-title">{task.prompt}</span>
                <span className="task-item-meta">
                  {shortId(task.task_id)} · {task.status}
                </span>
              </span>
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
