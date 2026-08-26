import type { TaskEvent, TaskRecord } from "@/types";
import { formatTime } from "@/utils/time";
import { formatAgents, getAgentNames } from "@/utils/task";

type TaskActivityProps = {
  task: TaskRecord | undefined;
};

/** Maps status/stage combos to dot colour classes. */
const MARK_COLOR: Record<string, string> = {
  running: "bg-[#5e5e58]",
  started: "bg-[#5e5e58]",
  completed: "bg-[#242422]",
  failed: "bg-[#b84343]",
  tool: "bg-[#3b82f6]",
  "tool-completed": "bg-[#10b981]",
};

function ActivityMark({
  status,
  isTool,
}: {
  status: string;
  isTool: boolean;
}) {
  let colorKey = status;
  if (isTool && status === "completed") colorKey = "tool-completed";
  else if (isTool) colorKey = "tool";

  const color = MARK_COLOR[colorKey] ?? "bg-[#b0b0aa]";

  return (
    <span
      aria-hidden="true"
      className={`z-10 flex-none w-2 h-2 mt-0.5 rounded-full border-2 border-white box-content ${color}`}
    />
  );
}

function ActivityEvent({ event }: { event: TaskEvent }) {
  const isTool = event.stage === "tool";

  return (
    <li className="grid grid-cols-[8px_minmax(0,1fr)_auto] gap-2 relative pb-[18px] last:pb-0">
      <ActivityMark status={event.status} isTool={isTool} />
      <div>
        <p
          className={`mb-[3px] text-xs font-bold capitalize ${
            isTool ? "text-[#2563eb] tracking-[0.02em] normal-case" : ""
          }`}
        >
          {isTool ? "tool" : event.stage}
        </p>
        <p className="mb-1 text-[#74746f] text-xs leading-[1.4]">
          {event.message}
        </p>
        {event.agent_id && (
          <code
            className={`text-[10px] text-[#5a5a54] font-mono overflow-wrap-anywhere ${
              isTool
                ? "inline-block px-[5px] py-[1px] rounded-[3px] bg-[#f0f0ec] text-[#4b5563]"
                : ""
            }`}
          >
            {isTool ? `by ${event.agent_id}` : event.agent_id}
          </code>
        )}
      </div>
      <time
        dateTime={event.occurred_at}
        className="text-[#74746f] text-[10px] whitespace-nowrap"
      >
        {formatTime(event.occurred_at)}
      </time>
    </li>
  );
}

export function TaskActivity({ task }: TaskActivityProps) {
  const latestEvent = task?.events.at(-1);
  const agents = task ? getAgentNames(task) : [];

  return (
    <aside className="bg-white border-l border-[#deded9] px-4 py-[22px] h-dvh overflow-y-auto min-w-0">
      {/* Panel heading */}
      <div className="mt-0 mb-2.5 mx-2 text-[#74746f] text-[11px] font-bold tracking-[0.08em] uppercase">
        Task activity
      </div>

      {!task ? (
        <p className="mx-2 text-[#74746f] text-xs leading-relaxed">
          Select or create a task to inspect it.
        </p>
      ) : (
        <>
          {/* Task summary */}
          <div className="flex gap-2 mx-2 mb-5">
            <span
              aria-hidden="true"
              className={`flex-none w-2 h-2 mt-[5px] rounded-full ${
                task.status === "running"
                  ? "bg-[#5e5e58]"
                  : task.status === "completed"
                    ? "bg-[#242422]"
                    : task.status === "failed"
                      ? "bg-[#b84343]"
                      : "bg-[#b0b0aa]"
              }`}
            />
            <div>
              <p className="m-0 mb-1 text-sm capitalize">{task.status}</p>
              <code className="text-[10px] text-[#5a5a54] font-mono overflow-wrap-anywhere">
                {task.task_id}
              </code>
            </div>
          </div>

          {/* Task facts */}
          <dl className="grid gap-[11px] mx-2 mb-[21px]">
            <div className="border-b border-[#f0f0ec] pb-2">
              <dt className="mb-[3px] text-[#74746f] text-[10px] font-bold tracking-[0.06em] uppercase">
                Current step
              </dt>
              <dd className="m-0 text-xs leading-[1.45] break-all">
                {latestEvent?.message ?? "Waiting to start."}
              </dd>
            </div>
            <div className="border-b border-[#f0f0ec] pb-2">
              <dt className="mb-[3px] text-[#74746f] text-[10px] font-bold tracking-[0.06em] uppercase">
                Agents
              </dt>
              <dd className="m-0 text-xs leading-[1.45] break-all">
                {formatAgents(agents, task.status)}
              </dd>
            </div>
            <div className="border-b border-[#f0f0ec] pb-2">
              <dt className="mb-[3px] text-[#74746f] text-[10px] font-bold tracking-[0.06em] uppercase">
                Activity
              </dt>
              <dd className="m-0 text-xs leading-[1.45] break-all">
                {task.events.length} events recorded
              </dd>
            </div>
            <div className="border-b border-[#f0f0ec] pb-2">
              <dt className="mb-[3px] text-[#74746f] text-[10px] font-bold tracking-[0.06em] uppercase">
                Submitted
              </dt>
              <dd className="m-0 text-xs leading-[1.45] break-all">
                {formatTime(task.submittedAt)}
              </dd>
            </div>
          </dl>

          {/* Timeline heading */}
          <div className="mt-0 mb-2.5 mx-2 text-[#74746f] text-[11px] font-bold tracking-[0.08em] uppercase">
            Timeline
          </div>

          {/* Event list */}
          <ol
            className="relative grid gap-0 m-0 list-none px-2 py-0
              before:content-[''] before:absolute before:top-[5px] before:bottom-[10px] before:left-[11px] before:w-px before:bg-[#deded9]"
          >
            {task.events.length === 0 ? (
              <li className="text-[#74746f] text-xs leading-relaxed">
                Waiting for task activity.
              </li>
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
  );
}
