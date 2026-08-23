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

function getAgentNames(task: TaskRecord) {
  return [
    ...new Set(
      task.events
        .filter((event) => event.agent_id)
        .map((event) => event.stage),
    ),
  ];
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
  const latestEvent = task?.events.at(-1);
  const agents = task ? getAgentNames(task) : [];

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
          <dl className="task-facts">
            <div>
              <dt>Current step</dt>
              <dd>{latestEvent?.message ?? "Waiting to start."}</dd>
            </div>
            <div>
              <dt>Agents</dt>
              <dd>{agents.length ? agents.join(", ") : "Not selected yet"}</dd>
            </div>
            <div>
              <dt>Activity</dt>
              <dd>{task.events.length} events recorded</dd>
            </div>
            <div>
              <dt>Submitted</dt>
              <dd>{formatTime(task.submittedAt)}</dd>
            </div>
          </dl>
          <div className="panel-heading timeline-heading">Timeline</div>
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
