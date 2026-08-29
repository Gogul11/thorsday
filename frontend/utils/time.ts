/**
 * Formats an ISO timestamp string to a human-readable time (HH:MM:SS).
 */
export function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}
