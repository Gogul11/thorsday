"""WebSocket registry — module-level store for active connections.

Each req_id can have multiple simultaneous WebSocket connections
(e.g. multiple browser tabs watching the same task).
Also buffers past events per req_id to replay them to late-connecting clients.
"""

import asyncio
import json

from fastapi import WebSocket

# req_id → list of live WebSocket connections
_connections: dict[str, list[WebSocket]] = {}

# req_id → list of past events (to replay if client connects slightly after task start)
_event_buffer: dict[str, list[dict]] = {}


async def ws_connect(req_id: str, websocket: WebSocket) -> None:
    """Accept the WebSocket handshake and register it under *req_id*."""
    """Accept the WebSocket handshake, register it under *req_id*, and replay buffered events."""
    await websocket.accept()
    _connections.setdefault(req_id, []).append(websocket)

    # Replay any events that were already broadcast before the client finished connecting
    buffered = _event_buffer.get(req_id, [])
    for event in buffered:
        try:
            await websocket.send_text(json.dumps(event))
        except Exception:
            break


def ws_disconnect(req_id: str, websocket: WebSocket) -> None:
    """Remove *websocket* from the registry; clean up the bucket if empty."""
    bucket = _connections.get(req_id, [])
    if websocket in bucket:
        bucket.remove(websocket)
    if not bucket:
        _connections.pop(req_id, None)


async def _cleanup_buffer(req_id: str, delay: int = 60) -> None:
    """Clean up the event buffer after a delay to prevent memory leaks."""
    await asyncio.sleep(delay)
    _event_buffer.pop(req_id, None)


async def ws_broadcast(req_id: str, data: dict) -> None:
    """Send a JSON message to every connection watching *req_id*.
    """Send a JSON message to every connection watching *req_id* and buffer it for late joiners."""
    # Store in buffer
    buffer = _event_buffer.setdefault(req_id, [])
    buffer.append(data)

    Dead connections are silently removed.
    """
    # If task is terminal, schedule buffer cleanup
    if data.get("event") in ("task.COMPLETED", "task.FAILED", "agent.FAILED"):
        asyncio.create_task(_cleanup_buffer(req_id, 60))

    dead: list[WebSocket] = []
    for ws in list(_connections.get(req_id, [])):
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_disconnect(req_id, ws)
