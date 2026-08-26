import type { KernelMessage } from "@/types";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// Derive ws:// / wss:// from the HTTP API URL
const wsBase = apiUrl.replace(/^http/, "ws");

/**
 * Opens a WebSocket to `/ws/<reqId>` and calls `onMessage` for every kernel
 * event that arrives.  Returns a cleanup function that closes the socket.
 *
 * Reconnects automatically with exponential back-off on unexpected closes
 * (code !== 1000).
 */
export function subscribeToTask(
  reqId: string,
  onMessage: (msg: KernelMessage) => void,
): () => void {
  const ws = new WebSocket(`${wsBase}/ws/${reqId}`);

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data as string) as KernelMessage;
      onMessage(msg);
    } catch {
      // malformed frame – ignore
    }
  };

  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;
  let delay = 1_000;

  ws.onclose = (ev) => {
    if (closed) return;
    // 1000 = normal closure (task done / navigated away); don't reconnect
    if (ev.code === 1000) return;
    reconnectTimer = setTimeout(() => {
      if (!closed) subscribeToTask(reqId, onMessage);
    }, delay);
    delay = Math.min(delay * 2, 30_000);
  };

  return () => {
    closed = true;
    if (reconnectTimer !== null) clearTimeout(reconnectTimer);
    ws.close(1000, "cleanup");
  };
}
