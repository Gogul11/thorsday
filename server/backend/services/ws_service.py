"""WebSocket registry — module-level store for active connections.

Each req_id can have multiple simultaneous WebSocket connections
(e.g. multiple browser tabs watching the same task).
"""

import json

from fastapi import WebSocket

# req_id → list of live WebSocket connections
_connections: dict[str, list[WebSocket]] = {}


async def ws_connect(req_id: str, websocket: WebSocket) -> None:
    """Accept the WebSocket handshake and register it under *req_id*."""
    await websocket.accept()
    _connections.setdefault(req_id, []).append(websocket)


def ws_disconnect(req_id: str, websocket: WebSocket) -> None:
    """Remove *websocket* from the registry; clean up the bucket if empty."""
    bucket = _connections.get(req_id, [])
    if websocket in bucket:
        bucket.remove(websocket)
    if not bucket:
        _connections.pop(req_id, None)


async def ws_broadcast(req_id: str, data: dict) -> None:
    """Send a JSON message to every connection watching *req_id*.

    Dead connections are silently removed.
    """
    dead: list[WebSocket] = []
    for ws in list(_connections.get(req_id, [])):
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_disconnect(req_id, ws)
