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
};

function shortId(taskId: string) {
  return taskId.split("-")[0];
}

export function TaskList({
  tasks,
  selectedTaskId,
  onSelect,
  onNewTask,
}: TaskListProps) {
  return (
    <aside className="sidebar">
      <div className="product-name">AgentOS</div>
      <button className="new-task-button" type="button" onClick={onNewTask}>
        + New task
      </button>

      <div className="sidebar-heading">Tasks</div>
      <div className="task-list">
        {tasks.length === 0 ? (
          <p className="empty-sidebar">Tasks you send will appear here.</p>
        ) : (
          tasks.map((task) => (
            <button
              className={`task-item ${task.task_id === selectedTaskId ? "selected" : ""}`}
              key={task.task_id}
              type="button"
              onClick={() => onSelect(task.task_id)}
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
