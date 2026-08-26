import type { TaskEvent, TaskRecord } from '@/lib/types'

type TaskActivityProps = {
  task: TaskRecord | undefined
}

function formatTime (value: string) {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(new Date(value))
}

function getAgentNames (task: TaskRecord): string[] {
  const names = new Set<string>()

  for (const event of task.events) {
    if (event.agent_id) {
      // Strip task_id prefix if present (e.g. "<task_id>-a3" -> "a3")
      const cleanName =
        event.agent_id.includes('-') && event.agent_id.startsWith(task.task_id)
          ? event.agent_id.slice(task.task_id.length + 1)
          : event.agent_id
      if (cleanName && cleanName !== 'agent' && cleanName !== 'task') {
        names.add(cleanName)
      }
    }
    // Also parse planned agents from "Plan ready: ['a1', 'a3']"
    if (event.message?.startsWith('Plan ready:')) {
      const match = event.message.match(/Plan ready:\s*\[(.*?)\]/)
      if (match && match[1]) {
        match[1]
          .split(',')
          .map(s => s.replace(/['"\s]/g, ''))
          .filter(Boolean)
          .forEach(agent => names.add(agent))
      }
    }
  }

  return Array.from(names)
}

function formatAgents (agents: string[], status: string): string {
  if (agents.length > 0) {
    return agents.join(', ')
  }
  if (status === 'completed') {
    return 'None (Direct response)'
  }
  return 'Not selected yet'
}

function ActivityEvent({ event }: { event: TaskEvent }) {
  const isTool = event.stage === "tool";

  return (
    <li className={`activity-event ${isTool ? "tool-event" : ""}`}>
      <span
        className={`activity-mark ${event.status} ${isTool ? "tool" : ""}`}
        aria-hidden="true"
      />
      <div>
        <p className={`activity-title ${isTool ? "tool-title" : ""}`}>
          {isTool ? "tool" : event.stage}
        </p>
        <p className="activity-message">{event.message}</p>
        {event.agent_id ? (
          <code className={isTool ? "tool-agent-badge" : ""}>
            {isTool ? `by ${event.agent_id}` : event.agent_id}
          </code>
        ) : null}
      </div>
      <time dateTime={event.occurred_at}>{formatTime(event.occurred_at)}</time>
    </li>
  );
}

export function TaskActivity ({ task }: TaskActivityProps) {
  const latestEvent = task?.events.at(-1)
  const agents = task ? getAgentNames(task) : []

  return (
    <aside className='activity-panel'>
      <div className='panel-heading'>Task activity</div>

      {!task ? (
        <p className='empty-activity'>Select or create a task to inspect it.</p>
      ) : (
        <>
          <div className='task-summary'>
            <span className={`status-dot ${task.status}`} aria-hidden='true' />
            <div>
              <p>{task.status}</p>
              <code>{task.task_id}</code>
            </div>
          </div>

          <dl className='task-facts'>
            <div>
              <dt>Current step</dt>
              <dd>{latestEvent?.message ?? 'Waiting to start.'}</dd>
            </div>
            <div>
              <dt>Agents</dt>
              <dd>{formatAgents(agents, task.status)}</dd>
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

          <div className='panel-heading timeline-heading'>Timeline</div>
          <ol className='activity-list'>
            {task.events.length === 0 ? (
              <li className='empty-activity'>Waiting for task activity.</li>
            ) : (
              task.events.map((event, index) => (
                <ActivityEvent
                  key={`${event.occurred_at}-${index}`}
                  event={event}
                />
              ))
            )}
          </ol>
        </>
      )}
    </aside>
  )
}
