/**
 * Formats an ISO timestamp string, numeric epoch timestamp, or Date to a human-readable time (HH:MM:SS).
 * Returns a fallback value if the timestamp is invalid or missing.
 */
export function formatTime(value: string | number | Date | null | undefined): string {
  if (!value) {
    return "--:--:--";
  }

  const date =
    value instanceof Date
      ? value
      : typeof value === "number"
        ? new Date(value < 1e11 ? value * 1000 : value)
        : new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "--:--:--";
  }

  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}
