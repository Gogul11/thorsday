# Backend Documentation

The backend is a FastAPI application. It is a thin relay layer — it does not execute
tasks, does not run agents, and does not own task state. Its only jobs are:

1. Accept HTTP requests from the frontend and publish them to the kernel via Redis.
2. Stream live kernel events back to the browser over WebSockets.
3. Serve task history from MongoDB for the sidebar on page load.

---

## How to run

```bash
# from server/
uvicorn main:app --reload

# or from server/backend/
uvicorn index:app --reload
```

---

## Directory map

```
server/backend/
├── index.py                         # FastAPI app factory + lifespan
│
├── DB/
│   └── mongodb.py                   # Motor client for backend reads
│
├── Redis/
│   └── redis_connection.py          # Redis client: publish + subscribe
│
├── routes/
│   └── task_routes.py               # All HTTP + WebSocket endpoints
│
├── controller/
│   └── task_controller.py           # POST /task business logic
│
├── schemas/
│   └── task.py                      # Pydantic request/response models
│
└── services/
    ├── ws_service.py                # WebSocket connection registry
    ├── kernel_listener.py           # Redis subscriber → WS broadcaster
    └── task_query_service.py        # MongoDB read helpers for GET routes
```

---

## File-by-file reference

---

### `index.py`

**Role:** Application factory. Creates the FastAPI app, registers middleware,
mounts routes, and manages the lifespan.

**`create_app()`:**
- Creates the `FastAPI` instance with title, description, and version.
- Adds `CORSMiddleware` — allowed origins read from `CORS_ORIGINS` env var
  (defaults to `localhost:3000`).
- Mounts the task router (`/task`, `/ws/{req_id}`, `/tasks`, `/tasks/{task_id}`).

**`lifespan(app)` (async context manager):**
- On startup: calls `start_kernel_listener()` which spawns the Redis subscriber
  as a background `asyncio.Task`.
- On shutdown: cancels the listener task and closes the Redis client.

**Entry point for `server/main.py`:**
`server/main.py` adds `server/backend/` to `sys.path` and re-exports `app` from
here, so `uvicorn main:app` works from the `server/` directory.

---

### `DB/mongodb.py`

**Role:** Motor (async MongoDB) client for backend read operations.

**What it does:**
- Reads `MONGO_URI` from environment (defaults to `mongodb://localhost:27017`).
- Creates one `AsyncIOMotorClient` at import time.
- Exposes `tasks_collection` — the same `agentos.tasks` collection the kernel writes to.

**Important:** The backend only reads from this collection. All writes are done
by the kernel. This preserves the single-writer principle.

**Used by:** `services/task_query_service.py`.

---

### `Redis/redis_connection.py`

**Role:** Async Redis client with `publish` and `subscribe` helpers.

**What it does:**
- `_get_client()` — lazy singleton that creates the `redis.asyncio.Redis` instance
  on first use (host `localhost`, port `6379`).
- `redis_publish(channel, data)` — serializes `data` to JSON and publishes it.
- `redis_subscribe(channel, handler)` — subscribes to `channel` and calls
  `handler(data)` for every incoming message. Runs indefinitely.
  Logs and continues on handler exceptions — never crashes the listener loop.
- `redis_close()` — closes the shared client cleanly on shutdown.

**Channels used by the backend:**
| Direction | Channel | Purpose |
|---|---|---|
| Writes | `backend_tasks` | Sends task requests to the kernel |
| Reads | `kernel_events` | Receives lifecycle events from the kernel |

**Used by:** `controller/task_controller.py` (publish), `services/kernel_listener.py` (subscribe).

---

### `schemas/task.py`

**Role:** Pydantic models for request validation and response serialization.

**Models:**

**`TaskRequest`** — body for `POST /task`:
```python
{
    "prompt":  str,           # required, min length 1
    "task_id": str = ""       # optional — empty for new task, set for follow-up
}
```

**`TaskResponse`** — immediate response from `POST /task`:
```python
{
    "req_id": str,            # UUID — open WS /ws/{req_id} to get live events
    "status": str             # always "queued" on creation
}
```

**`TaskSummary`** — one row in `GET /tasks` (informational, not used as response_model):
```python
{
    "task_id":    str,
    "title":      str,
    "status":     str,
    "plan":       list[str],
    "response":   str | None,
    "created_at": str
}
```

**`KernelEvent`** — shape of messages pushed over the WebSocket (informational):
```python
{
    "event":   str,
    "req_id":  str,
    "task_id": str
}
```

---

### `routes/task_routes.py`

**Role:** Declares all HTTP and WebSocket routes. No logic lives here — each
route delegates immediately to a controller or service function.

**Endpoints:**

| Method | Path | Handler | Description |
|---|---|---|---|
| `POST` | `/task` | `create_task_handler` | Submit a new task or follow-up message. Returns `{req_id, status}`. |
| `WS` | `/ws/{req_id}` | `ws_connect` / `ws_disconnect` | Stream kernel events for `req_id`. Backend pushes; client just keeps the connection open. |
| `GET` | `/tasks` | `get_all_tasks` | List all tasks newest-first. Used to populate the sidebar on page load. |
| `GET` | `/tasks/{task_id}` | `get_task_by_id` | Full task detail including `messages[]`. Returns 404 if not found. |

**WebSocket lifecycle:**
1. `ws_connect(req_id, websocket)` — accepts the handshake, registers it in `ws_service`.
2. `await websocket.receive_text()` in a loop — keeps the connection alive,
   raises `WebSocketDisconnect` when the client closes.
3. `ws_disconnect(req_id, websocket)` — removes the connection from the registry.

---

### `controller/task_controller.py`

**Role:** HTTP handler logic for `POST /task`.

**`create_task_handler(request)`:**
1. Generates a UUID `req_id`. This is the transient WebSocket subscription key —
   it lives only for the duration of one request/response cycle.
2. Publishes `task.REQUESTED` to the `backend_tasks` Redis channel with:
   - `req_id` — so the kernel can include it in every event it emits
   - `prompt` — the user's message
   - `task_id` — empty string for new tasks, existing UUID for follow-ups
3. Returns `TaskResponse(req_id=req_id, status="queued")` immediately.
   The actual task execution is asynchronous — the frontend gets results via WebSocket.

**Why `req_id` is separate from `task_id`:**
- `task_id` is the persistent MongoDB document ID. It stays the same across all
  follow-up messages in a conversation.
- `req_id` is freshly generated for every POST call. It is the key used to
  route kernel events to the right WebSocket connection for that specific request.

---

### `services/ws_service.py`

**Role:** In-memory WebSocket connection registry.

**State:** Module-level `_connections` dict — `req_id → list[WebSocket]`.
Multiple browser tabs can watch the same `req_id` simultaneously.

**Functions:**

| Function | Description |
|---|---|
| `ws_connect(req_id, websocket)` | Accepts the WS handshake and appends the socket to `_connections[req_id]`. |
| `ws_disconnect(req_id, websocket)` | Removes the socket. Cleans up the bucket if it becomes empty. |
| `ws_broadcast(req_id, data)` | Sends `json.dumps(data)` to every socket watching `req_id`. Silently removes dead connections that raise on send. |

**Used by:** `routes/task_routes.py` (connect/disconnect), `services/kernel_listener.py` (broadcast).

---

### `services/kernel_listener.py`

**Role:** Bridges the kernel's Redis events to the browser's WebSocket connections.

**`handle_kernel_event(data)`:**
- Extracts `req_id` from the event payload.
- Calls `ws_broadcast(req_id, data)` to forward the raw event to all WebSocket
  clients subscribed to that `req_id`.
- No transformation — the full kernel event is forwarded as-is.

**`start_kernel_listener()`:**
- Wraps `redis_subscribe("kernel_events", handle_kernel_event)` in an
  `asyncio.Task` named `"kernel_listener"`.
- Returns the task so `index.py` can cancel it on shutdown.

**Used by:** `index.py` lifespan.

---

### `services/task_query_service.py`

**Role:** Read-only MongoDB helpers for the `GET /tasks` and `GET /tasks/{task_id}` routes.

**`get_all_tasks()`:**
- Queries `tasks_collection` for all documents, projecting only summary fields.
- Sorts newest-first (`created_at: -1`), limit 200.
- Serializes `datetime` objects to ISO strings before returning.
- Returns a plain `list[dict]` — FastAPI serializes it to JSON automatically.

**`get_task_by_id(task_id)`:**
- Fetches the full document for `task_id`.
- Serializes all `datetime` fields (top-level, inside `messages[]`, inside `events[]`).
- Returns `None` if not found — the route layer converts that to a 404.

---

## Request lifecycle (end-to-end)

### New task

```
Browser
  POST /task {prompt: "...", task_id: ""}
    ↓
controller/task_controller.py
  → generate req_id
  → redis_publish("backend_tasks", {event: "task.REQUESTED", req_id, prompt, task_id: ""})
  → return {req_id, status: "queued"}

Browser
  WS /ws/{req_id}
    ↓
services/ws_service.py — ws_connect(req_id, ws)

Kernel (separate process)
  receives "task.REQUESTED" on backend_tasks
  → dispatcher.py → task_runner.py → graph runs
  → publishes to kernel_events: task.CREATED, task.PLANNING, task.PLANNED,
    agent.STARTED, tool.STARTED, tool.COMPLETED, agent.COMPLETED, task.COMPLETED

Backend kernel_listener
  receives each event from kernel_events
  → ws_broadcast(req_id, event) → browser WebSocket
```

### Follow-up message

```
Browser (selected task has task_id = "abc-123", status = "completed")
  POST /task {prompt: "tell me more", task_id: "abc-123"}
    ↓
controller → new req_id generated
  → redis_publish({event: "task.REQUESTED", req_id: NEW, prompt, task_id: "abc-123"})

Kernel
  receives task.REQUESTED with task_id="abc-123"
  → dispatcher → run_task(prompt, req_id=NEW, task_id="abc-123")
  → get_context("abc-123") loads prior messages[]
  → graph reuses existing MongoDB document (skips DB_create_task)
  → appends new human + AI messages to the same task document
  → publishes events with req_id=NEW so the new WS connection gets them

Browser
  WS /ws/{req_id=NEW}
  receives events → UI shows the new response appended to the existing conversation
```

### Page load (history)

```
Browser mounts
  GET /tasks
    ↓
task_query_service.get_all_tasks()
  → MongoDB find all, sort by created_at desc
  → returns [{task_id, title, status, plan, response, created_at}, ...]
  → sidebar populated with all previous tasks

User clicks a task in the sidebar
  GET /tasks/{task_id}
    ↓
task_query_service.get_task_by_id(task_id)
  → returns full document including messages[]
  → frontend renders full conversation history
```

---

## Environment variables

| Variable | Used in | Description |
|---|---|---|
| `MONGO_URI` | `DB/mongodb.py` | MongoDB connection string. Default: `mongodb://localhost:27017` |
| `CORS_ORIGINS` | `index.py` | Comma-separated allowed origins. Default: `http://localhost:3000,http://127.0.0.1:3000` |

Redis connection is hardcoded to `localhost:6379` — move to env if deploying remotely.
