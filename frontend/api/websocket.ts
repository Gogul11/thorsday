import type { KernelEvent } from "@/types";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const wsBase = apiUrl.replace(/^http/, "ws");

/**
 * Opens a WebSocket to `/ws/{reqId}` and calls `onMessage` for every raw
 * kernel event that arrives.  Returns a cleanup function that closes the
 * socket cleanly.
 *
 * On unexpected disconnects (code !== 1000) the socket is reconnected with
 * exponential back-off up to 30 s.
 */
export function subscribeToTask(
  reqId: string,
  onMessage: (event: KernelEvent) => void,
): () => void {
  let closed = false;
  let delay = 1_000;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let ws: WebSocket;

  function connect() {
    ws = new WebSocket(`${wsBase}/ws/${reqId}`);

    ws.onmessage = (frame) => {
      try {
        const event = JSON.parse(frame.data as string) as KernelEvent;
        onMessage(event);
      } catch {
        // malformed frame — ignore
      }
    };

    ws.onclose = (ev) => {
      if (closed) return;
      // 1000 = normal closure (caller called cleanup or task is done)
      if (ev.code === 1000) return;
      reconnectTimer = setTimeout(() => {
        if (!closed) connect();
      }, delay);
      delay = Math.min(delay * 2, 30_000);
    };
  }

  connect();

  return () => {
    closed = true;
    if (reconnectTimer !== null) clearTimeout(reconnectTimer);
    ws?.close(1000, "cleanup");
  };
}
