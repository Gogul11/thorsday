# Backend & Frontend Rewrite Summary

## Backend Changes (server/backend/)

### Architecture shift
- **Removed in-memory task repository** — the kernel owns task state, backend is now a thin pub/sub relay + WebSocket broadcaster
- **Switched from task_id-keyed endpoints to req_id-keyed WebSockets** — backend generates `req_id`, kernel assigns `task_id` later
- **All state derived from kernel events** — no shadow state, no REST polling

### Deleted files
```
repo/                     # in-memory task store
svc/                      # old redis + ws + handler blob
services/task_service.py  # old service layer
```

### New structure
```
backend/
├── index.py                    # app factory + lifespan
├── Redis/
│   └── redis_connection.py    # lazy singleton: publish / subscribe / close
├── routes/
│   └── task_routes.py          # POST /task  +  WS /ws/{req_id}
├── controller/
│   └── task_controller.py      # generate req_id, publish to kernel, return
├── schemas/
│   └── task.py                 # TaskRequest, TaskResponse, KernelEvent
└── services/
    ├── ws_service.py           # WebSocket registry
    └── kernel_listener.py      # subscribe kernel_events → ws_broadcast
```

### API contract
**POST /task**
```json
Request:  { "prompt": "..." }
Response: { "req_id": "<uuid>", "status": "queued" }
```

**WS /ws/{req_id}**
- Client opens WebSocket using `req_id` from POST response
- Server pushes raw kernel events as-is:
  ```json
  {
    "event": "task.CREATED" | "task.PLANNING" | "task.PLANNED" | 
             "task.COMPLETED" | "agent.STARTED" | "agent.COMPLETED" | 
             "agent.FAILED" | "agent.DESTROYED" | 
             "tool.STARTED" | "tool.COMPLETED" | "tool.FAILED",
    "req_id": "<uuid>",
    "task_id": "<uuid>",
    "plan": [...],           // task.PLANNED
    "agent_name": "...",     // agent.* / tool.*
    "response": "...",       // task.COMPLETED
    "error": "..."           // *.FAILED
  }
  ```

**Removed endpoints**
- `GET /status/{task_id}` — polling replaced by WebSocket

### Redis channels
- **backend → kernel**: `backend_tasks`
  - Published: `{ event: "task.REQUESTED", req_id, prompt }`
- **kernel → backend**: `kernel_events`
  - Subscribed: all kernel lifecycle events

---

## Frontend Changes (frontend/)

### Type system changes (types/index.ts)
```typescript
// Raw event shape from WebSocket
type KernelEvent = {
  event: "task.CREATED" | "agent.STARTED" | ...
  req_id: string
  task_id: string
  plan?: string[]
  agent_name?: string
  response?: string
  error?: string
  // ... event-specific fields
}

// Normalized display event for UI components
type DisplayEvent = {
  stage: "task" | "agent" | "tool"
  status: "created" | "started" | "failed" | ...
  message: string
  occurred_at: string
  agent_id: string | null
  raw_event: string
}

// Client-side task record
type TaskRecord = {
  req_id: string        // returned by POST /task
  task_id: string       // filled in by kernel's first event
  prompt: string
  submittedAt: string
  status: string
  response: string | null
  error: string | null
  events: DisplayEvent[]
  plan: string[]        // from task.PLANNED
}
```

### API layer changes
- **api/tasks.ts**: `createTask` returns `{req_id, status}`; `getTaskStatus` removed
- **api/websocket.ts**: `subscribeToTask(reqId, onMessage)` emits raw `KernelEvent`

### Hook changes (hooks/useTaskSubscriptions.ts)
- Subscribes by `req_id` instead of `task_id`
- Translates raw `KernelEvent` → `DisplayEvent` with human-readable messages
- Derives `status`, `response`, `error`, `task_id`, and `plan` from event stream
- Closes WebSocket when task reaches terminal state

### Component changes
- **TaskActivity**: renders `DisplayEvent[]`, uses `shortId(task.req_id)` for ID display
- **TaskList**: keyed by `req_id`, accepts `selectedReqId` prop
- **ChatPage**: local state uses `req_id` as primary key, constructs `TaskRecord` with empty `task_id` / `plan` until filled by kernel

### Utils changes (utils/task.ts)
- `getAgentNames(task)`: reads `task.plan` first (from `task.PLANNED` event), falls back to extracting `agent_id` from display events
- `formatAgents`, `shortId`: unchanged in signature

---

## Data flow (end-to-end)

1. **User submits prompt**  
   → Frontend: `POST /task {prompt}`  
   → Backend: generates `req_id`, publishes `task.REQUESTED` to Redis  
   → Returns `{req_id, status: "queued"}`

2. **Frontend opens WebSocket**  
   → `WS /ws/{req_id}`

3. **Kernel receives task**  
   → Creates `task_id`, starts planning  
   → Publishes events to `kernel_events` channel:
   - `task.CREATED`
   - `task.PLANNING`
   - `task.PLANNED` (includes `plan: ["a1", "a3"]`)
   - `agent.STARTED`
   - `tool.STARTED` / `tool.COMPLETED`
   - `agent.COMPLETED`
   - `task.COMPLETED` (includes `response`)

4. **Backend relays events**  
   → `kernel_listener` receives from Redis  
   → `ws_broadcast(req_id, event)` pushes to browser

5. **Frontend updates UI**  
   → Hook translates `KernelEvent` → `DisplayEvent`  
   → Merges into `TaskRecord.events[]`  
   → Derives `status`, `plan`, `response`  
   → Components re-render with live data

---

## Verification

**Backend**
- ✓ All 13 Python files pass AST syntax check
- ✓ Full import chain resolves cleanly
- ✓ `POST /task` and `WS /ws/{req_id}` routes confirmed in FastAPI router

**Frontend**
- ✓ TypeScript compiles with no errors (`tsc --noEmit`)
- ✓ All component prop types updated to use `req_id`
- ✓ Event translation logic in hook preserves all kernel event data

---

## Run instructions

**Backend** (from `server/`)
```bash
uvicorn main:app --reload
```

**Frontend** (from `frontend/`)
```bash
npm run dev
```

The frontend will connect to `http://127.0.0.1:8000` by default (configurable via `NEXT_PUBLIC_API_URL`).
