# Kernel Documentation

The kernel is an independent Python process. It owns all agent execution, all
MongoDB writes, and all LangGraph orchestration. The backend never calls the
kernel directly — they communicate exclusively through Redis pub/sub.

---

## How to run

```bash
# from server/
python kernel/main.py
```

---

## Directory map

```
server/kernel/
├── main.py                          # entry point — startup only
├── logger.py                        # shared logger config
│
├── DB/
│   └── mongodb.py                   # Motor client + tasks_collection
│
├── Redis/
│   └── redis_connection.py          # redis client + publish/subscribe/close
│
├── models/
│   └── model.py                     # LLM factory (get_model)
│
├── repository/
│   └── task_repo.py                 # all MongoDB read/write functions
│
├── services/
│   ├── context.py                   # conversation context helpers
│   ├── task_runner.py               # graph execution + message persistence
│   └── dispatcher.py               # Redis event routing
│
├── graphs/
│   ├── main_agent_graph.py          # build_graph() — the LangGraph pipeline
│   └── states/
│       └── main_agent_state.py     # MainAgentState TypedDict
│
├── Agents/
│   ├── agent_registry.py            # registry of agent types
│   ├── agent_manager.py             # runtime lifecycle of active agents
│   ├── main_agent.py                # (empty — replaced by task_runner.py)
│   └── agents/
│       ├── a1.py                    # system-info agent
│       ├── a2.py                    # date/time agent
│       └── a3.py                    # research agent
│
└── tools/
    ├── tool_registry.py             # A1_TOOLS / A2_TOOLS / A3_TOOLS lists
    ├── sys_info_tools.py            # get_system_info tool
    ├── time_tool.py                 # get_time tool
    └── research_tools.py            # wikipedia_search, trusted_web_search tools
```

---

## File-by-file reference

---

### `main.py`

**Role:** Entry point. Startup and connection checks only. No business logic.

**What it does:**
1. Configures stdout/stderr encoding on Windows.
2. Pings MongoDB and Redis — raises immediately if either is unreachable.
3. Calls `warmup()` to pre-build the LangGraph before the first request arrives.
4. Calls `subscribe("backend_tasks", handle_backend_task)` which blocks forever,
   passing every incoming Redis message to the dispatcher.

**What it does NOT do:** Execute tasks, parse events, touch MongoDB, touch the graph.

**Imports from:** `DB/mongodb.py`, `Redis/redis_connection.py`,
`services/dispatcher.py`, `services/task_runner.py`, `logger.py`

---

### `logger.py`

**Role:** Shared logging configuration.

**What it does:**
- Creates a logger named `"AOS"` at `INFO` level.
- Attaches a `FileHandler` writing to `kernel/logs/app.log`.
- Uses the format: `timestamp | LEVEL | AOS | message`.
- Guards against duplicate handlers if imported multiple times.

**Used by:** Every module that needs `from logger import logger`.

---

### `DB/mongodb.py`

**Role:** Motor (async MongoDB) client and collection references.

**What it does:**
- Reads `MONGO_URI` from environment.
- Creates one `AsyncIOMotorClient` instance at import time.
- Exposes `mongo_client` (used in `main.py` for the ping check) and
  `tasks_collection` (used by `task_repo.py` for all reads/writes).

**Database:** `agentos`
**Collection:** `tasks`

**Used by:** `main.py` (ping), `repository/task_repo.py` (all queries).

---

### `Redis/redis_connection.py`

**Role:** Shared async Redis client + `publish` / `subscribe` / `close` helpers.

**What it does:**
- Creates one `redis.asyncio.Redis` client at import time (host `localhost`, port `6379`).
- `publish(channel, data)` — serializes `data` to JSON and publishes it.
- `subscribe(channel, handler)` — subscribes and calls `handler(data)` for every
  message on the channel. Runs forever until the task is cancelled.
- `close()` — closes the client cleanly on shutdown.

**Channels used by the kernel:**
| Direction | Channel | Purpose |
|---|---|---|
| Reads | `backend_tasks` | Receives task requests from the backend |
| Writes | `kernel_events` | Publishes lifecycle events back to the backend |

**Used by:** `main.py`, `services/dispatcher.py`, `graphs/main_agent_graph.py`.

---

### `models/model.py`

**Role:** LLM factory — returns a configured `ChatGroq` instance.

**What it does:**
- `get_model()` — lazy singleton. On first call reads `GROQ_API_KEY` from env,
  creates a `ChatGroq` instance (`openai/gpt-oss-120b`, temperature 0.2),
  caches it in `_model`, and returns it. Subsequent calls return the cached instance.

**Why a function instead of a class:** No state to manage. A module-level singleton
function is simpler and easier to mock in tests.

**Used by:** `services/task_runner.py` → passed into `build_graph(model)`.

---

### `repository/task_repo.py`

**Role:** All MongoDB read/write operations for the `tasks` collection.

**Functions:**

| Function | Operation | Description |
|---|---|---|
| `DB_create_task(task_id, prompt)` | INSERT | Creates a new task document. Sets status `"running"`, stores first 80 chars of prompt as `title`, initializes empty `messages`, `events`, `plan`. |
| `DB_add_task_message(task_id, role, content)` | UPDATE `$push` | Appends one `{role, content, timestamp}` object to `messages[]`. Role is `"human"` or `"ai"`. |
| `DB_update_task(task_id, **values)` | UPDATE `$set` | Sets arbitrary fields on a task. Always sets `updated_at`. Used to persist `plan`, `status`, `response`, `completed_at`. |
| `DB_add_task_event(task_id, event)` | UPDATE `$push` | Appends one event dict to `events[]`. Adds `timestamp` automatically. |
| `DB_get_task_messages(task_id)` | FIND ONE | Returns `messages[]` for a task, or `None` if not found. Used by `get_context()` to load prior conversation. |
| `DB_get_all_tasks()` | FIND MANY | Returns all tasks newest-first, summary fields only (`task_id`, `title`, `status`, `plan`, `response`, `created_at`). Max 200. |
| `DB_get_task(task_id)` | FIND ONE | Returns the full task document including `messages[]` and `events[]`. |

**Task document shape:**
```python
{
    "task_id":       str,          # UUID — primary key
    "title":         str,          # first 80 chars of first prompt
    "status":        str,          # "running" | "completed" | "failed"
    "messages":      list[dict],   # [{role, content, timestamp}, ...]
    "plan":          list[str],    # ["a1", "a3"] — agents selected by planner
    "current_agent": int,          # index into plan during execution
    "agents":        dict,         # reserved
    "results":       dict,         # per-agent raw results
    "response":      str | None,   # final markdown response
    "events":        list[dict],   # all lifecycle events with timestamps
    "created_at":    datetime,
    "updated_at":    datetime,
    "completed_at":  datetime | None,
}
```

**Used by:** `services/context.py`, `graphs/main_agent_graph.py`.

---

### `services/context.py`

**Role:** Conversation context helpers — load and persist message history per task.

**Functions:**

| Function | Description |
|---|---|
| `get_context(task_id)` | Loads `messages[]` from MongoDB for `task_id`, converts them to LangChain `HumanMessage` / `AIMessage` objects, prepends the system prompt, and returns the last 20 entries. Returns `[SYSTEM_MESSAGE]` for brand-new tasks. |
| `add_user_message(task_id, content)` | Persists a `role="human"` message via `DB_add_task_message`. |
| `add_ai_message(task_id, content)` | Persists a `role="ai"` message via `DB_add_task_message`. |

**`SYSTEM_MESSAGE`:** The kernel-level system prompt that defines the main agent's
identity and rules. Injected at position 0 of every context window.

**Context window:** Capped at 20 messages (`_CONTEXT_WINDOW = 20`) to avoid
unbounded token growth across long conversations.

**Used by:** `services/task_runner.py`.

---

### `services/task_runner.py`

**Role:** Graph execution and message persistence. The main business logic hub.

**Functions:**

| Function | Description |
|---|---|
| `warmup()` | Calls `_get_graph()` at startup so the first real request doesn't pay the graph-build cost. |
| `_get_graph()` | Lazy singleton. Calls `get_model()` and `build_graph(model)` once, caches the compiled graph. |
| `run_task(prompt, req_id, task_id)` | Orchestrates one full task turn: loads context → invokes graph → persists human + AI messages → returns response string. |

**Flow inside `run_task`:**
```
1. If task_id is non-empty → call get_context(task_id) to load prior messages
2. Call graph.ainvoke({req_id, messages, task_id, task=prompt, ...})
3. Graph runs: task_creation → planner → executor(s) → response_node
   Each node publishes Redis events and writes to MongoDB independently
4. After graph returns → persist human message + AI response to messages[]
5. Return response string
```

**New task vs follow-up:**
- `task_id=""` → `_node_create_task` generates a new UUID and calls `DB_create_task`
- `task_id=<existing>` → `_node_create_task` skips creation, reuses the document

**Used by:** `services/dispatcher.py`.

---

### `services/dispatcher.py`

**Role:** Redis event router. Translates raw Redis messages into `run_task` calls.

**Functions:**

| Function | Description |
|---|---|
| `handle_backend_task(data)` | Called for every message on `backend_tasks`. Ignores events that aren't `"task.REQUESTED"`. Extracts `req_id`, `prompt`, `task_id` from the payload, calls `run_task()`. On any exception, publishes an `agent.FAILED` event to `kernel_events` so the frontend always gets a terminal event. |

**Why it's separate from `task_runner.py`:** The dispatcher knows about Redis event
shapes and error publishing. `task_runner.py` knows nothing about Redis. If a new
event type is added (e.g. `task.CANCELLED`), only the dispatcher changes.

**Used by:** `main.py`.

---

### `graphs/main_agent_graph.py`

**Role:** The LangGraph pipeline. Defines all graph nodes and wires them together.

**Public API:** `build_graph(model)` — returns a compiled `StateGraph`.

**Nodes:**

| Node | Function | Description |
|---|---|---|
| `task_creation` | `_node_create_task` | Creates a new MongoDB document for new tasks, or skips for follow-ups. Emits `task.CREATED`. |
| `planner` | `_node_planner` | Asks the LLM (with `with_structured_output(ExecutionPlan)`) which agents to run. Emits `task.PLANNING` then `task.PLANNED`. Persists `plan` to MongoDB. |
| `executor` | `_node_executor` | Runs the next agent in `plan[current_agent]`. Emits `agent.STARTED`, `agent.COMPLETED`/`FAILED`, `agent.DESTROYED`. Increments `current_agent`. |
| `response_node` | `_node_response` | Generates the final user-facing response using all agent results. Emits `task.COMPLETED`. Sets `status="completed"` and `completed_at` in MongoDB. |

**Graph edges:**
```
START → task_creation → planner
planner → executor   (if plan has agents)
planner → response_node (if plan is empty)
executor → executor  (loop while current_agent < len(plan))
executor → response_node (when all agents done)
response_node → END
```

**`_emit(event, state, **data)`:** Module-level helper that both publishes to Redis
`kernel_events` and appends to `DB_add_task_event`. Called by every node.

**`ToolEventCallback`:** `BaseCallbackHandler` subclass that bridges synchronous
LangChain tool callbacks into the async event loop via
`asyncio.run_coroutine_threadsafe`. Emits `tool.STARTED`, `tool.COMPLETED`,
`tool.FAILED`. Kept as a class because LangChain requires a class here.

**`ExecutionPlan`:** Pydantic model used with `with_structured_output` so the LLM
returns a typed list of agent identifiers instead of free text.

---

### `graphs/states/main_agent_state.py`

**Role:** Type definition for the LangGraph state dict.

**`MainAgentState` fields:**

| Field | Type | Description |
|---|---|---|
| `req_id` | `str` | Transient WS key. Never written to MongoDB — used only in Redis events. |
| `messages` | `list[BaseMessage]` | Conversation history for the LLM. Uses `add_messages` reducer (LangGraph appends, not replaces). |
| `task_id` | `str` | MongoDB task ID. Empty on entry for new tasks, filled by `task_creation` node. |
| `task` | `str` | The raw user prompt for this turn. |
| `plan` | `list[str]` | Agent identifiers chosen by the planner, e.g. `["a1", "a3"]`. |
| `current_agent` | `int` | Index into `plan`. Incremented by the executor after each agent completes. |
| `results` | `dict[str, str]` | Accumulated agent outputs, keyed by agent name. Passed as context to each subsequent agent. |
| `response` | `str` | Final response set by `response_node`. |

---

### `Agents/agent_registry.py`

**Role:** Static registry of all available agent types.

**What it contains:**
- `_REGISTRY` dict mapping agent type key → `{run: fn, description: str}`.
- `get_agent_run_fn(agent_type)` — returns the async run function for that type.
  Raises `ValueError` for unknown types.
- `get_agent_descriptions()` — returns `{type: description}` dict used in the
  planner prompt so the LLM knows what each agent does.
- `list_agent_types()` — returns all registered keys.

**To add a new agent:** Create `agents/aX.py` with `run_agent_aX` and
`AGENT_AX_DESCRIPTION`, then add one entry to `_REGISTRY`.

---

### `Agents/agent_manager.py`

**Role:** Runtime lifecycle tracking for agents that are currently executing.

**State:** Module-level `_agents` dict — `agent_id → runtime dict`. Only populated
during graph execution; empty between tasks.

**Functions:**

| Function | Description |
|---|---|
| `create_agent(agent_id, agent_type, task_id)` | Registers a new runtime entry. Looks up the run function from the registry. Raises if `agent_id` already exists. |
| `get_agent(agent_id)` | Returns the runtime dict for an active agent. |
| `set_agent_status(agent_id, status)` | Updates status to `"RUNNING"`, `"COMPLETED"`, or `"FAILED"`. |
| `destroy_agent(agent_id)` | Removes the agent from `_agents`. No-op if already gone. |

**`runtime` dict shape:**
```python
{
    "id":      agent_id,
    "type":    agent_type,   # "a1", "a2", "a3"
    "task_id": task_id,
    "run":     run_fn,       # the async run function from the registry
    "status":  "CREATED",
}
```

---

### `Agents/agents/a1.py`, `a2.py`, `a3.py`

Each agent is a single async function: `run_agent_aX(model, task, context, callbacks)`.

| Agent | File | Tools | Responsibility |
|---|---|---|---|
| A1 | `a1.py` | `get_system_info` | System information — OS, hardware, processes, environment |
| A2 | `a2.py` | `get_time` | Date and time queries |
| A3 | `a3.py` | `wikipedia_search`, `trusted_web_search` | Academic/factual research from trusted sources |

Each file also exports a `AGENT_AX_DESCRIPTION` string constant consumed by
`agent_registry.py` for the planner prompt.

**How a run function works:**
1. Calls `langchain.agents.create_agent(model, tools)` — creates a fresh ReAct agent.
2. Builds a prompt string combining the agent's description, the task, and
   results from prior agents.
3. Calls `agent.ainvoke({messages: [...]}, config={callbacks: ...})`.
4. Returns `result["messages"][-1].content` — the agent's final text output.

---

### `tools/tool_registry.py`

**Role:** Declares the tool lists given to each agent.

```python
A1_TOOLS = [get_system_info]
A2_TOOLS = [get_time]
A3_TOOLS = [wikipedia_search, trusted_web_search]
```

Imported by each agent file. Adding a new tool to an agent means adding it here.

---

### `tools/sys_info_tools.py`

**`get_system_info()`** — LangChain `@tool`. Returns OS name, release, architecture,
and processor as a plain string. Used by A1.

---

### `tools/time_tool.py`

**`get_time()`** — LangChain `@tool`. Returns current `datetime.now()` as a string.
Used by A2.

---

### `tools/research_tools.py`

Two LangChain `@tool` functions for A3:

**`wikipedia_search(query, max_results=3)`**
- Calls the Wikipedia REST API (`/w/api.php` search + `/api/rest_v1/page/summary`).
- Returns structured results: title, URL, extract/snippet for each article.

**`trusted_web_search(query, max_results=5, domains=None)`**
- Uses DuckDuckGo (`ddgs` / `duckduckgo-search` package) with `site:` filters
  restricted to `TRUSTED_DOMAINS`: arXiv, Nature, IEEE, Springer, NIH, ACM, etc.
- Two-pass strategy: combined `site:` OR query first, then individual domain
  fallbacks if no results.
- Filters results through `_is_trusted_domain_url` to strip ad/tracker links.

---

## Data flow (kernel perspective)

```
Redis 'backend_tasks'
    ↓ subscribe (redis_connection.py)
dispatcher.py — handle_backend_task()
    ↓ run_task(prompt, req_id, task_id)
task_runner.py
    ↓ get_context(task_id) [if follow-up]       ← services/context.py
    ↓ graph.ainvoke(state)
        ↓ _node_create_task → DB_create_task()   ← repository/task_repo.py
        ↓ _node_planner → LLM structured output
        ↓ _node_executor → run_agent_aX()        ← Agents/agents/
        ↓ _node_response → LLM final response
        Each node: _emit() → publish() + DB_add_task_event()
    ↓ add_user_message() + add_ai_message()     ← services/context.py
Redis 'kernel_events' → backend → WebSocket → browser
MongoDB 'tasks' collection → backend GET /tasks → browser on load
```
