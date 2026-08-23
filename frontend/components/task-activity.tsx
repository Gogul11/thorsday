import { TaskEvent } from "@/lib/api";
import { TaskRecord } from "./task-list";

type TaskActivityProps = {
  task: TaskRecord | undefined;
};

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function ActivityEvent({ event }: { event: TaskEvent }) {
  return (
    <li className="activity-event">
      <span className={`activity-mark ${event.status}`} aria-hidden="true" />
      <div>
        <p className="activity-title">{event.stage}</p>
        <p className="activity-message">{event.message}</p>
        {event.agent_id ? <code>{event.agent_id}</code> : null}
      </div>
      <time dateTime={event.occurred_at}>{formatTime(event.occurred_at)}</time>
    </li>
  );
}

export function TaskActivity({ task }: TaskActivityProps) {
  return (
    <aside className="activity-panel">
      <div className="panel-heading">Task activity</div>

      {!task ? (
        <p className="empty-activity">Select or create a task to inspect it.</p>
      ) : (
        <>
          <div className="task-summary">
            <span className={`status-dot ${task.status}`} aria-hidden="true" />
            <div>
              <p>{task.status}</p>
              <code>{task.task_id}</code>
            </div>
          </div>
          <ol className="activity-list">
            {task.events.length === 0 ? (
              <li className="empty-activity">Waiting for task activity.</li>
            ) : (
              task.events.map((event, index) => (
                <ActivityEvent key={`${event.occurred_at}-${index}`} event={event} />
              ))
            )}
          </ol>
        </>
      )}
    </aside>
  );
}
